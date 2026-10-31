"""Capture only the X11 surface owned by a native test process, even when unfocused."""
import ctypes as C
from PIL import Image
from vela.preview import XWindows

class XImage(C.Structure):
    _fields_=[('width',C.c_int),('height',C.c_int),('xoffset',C.c_int),('format',C.c_int),
              ('data',C.c_void_p),('byte_order',C.c_int),('bitmap_unit',C.c_int),
              ('bitmap_bit_order',C.c_int),('bitmap_pad',C.c_int),('depth',C.c_int),
              ('bytes_per_line',C.c_int),('bits_per_pixel',C.c_int),
              ('red_mask',C.c_ulong),('green_mask',C.c_ulong),('blue_mask',C.c_ulong)]

def client_pid(connection, window):
    # vkcube does not publish _NET_WM_PID. XRes can identify the X11 client
    # owning its resource, so we never fall back to capturing another app.
    class Spec(C.Structure):
        _fields_ = [('client', C.c_ulong), ('mask', C.c_ulong)]
    class Value(C.Structure):
        _fields_ = [('spec', Spec), ('length', C.c_long), ('value', C.c_void_p)]
    try:
        res = C.CDLL('libXRes.so.1')
    except OSError:
        return None
    res.XResQueryClientIds.argtypes = [C.c_void_p, C.c_long, C.POINTER(Spec), C.POINTER(C.c_long), C.POINTER(C.POINTER(Value))]
    res.XResGetClientPid.argtypes = [C.POINTER(Value)]
    res.XResGetClientPid.restype = C.c_int
    res.XResClientIdsDestroy.argtypes = [C.c_long, C.POINTER(Value)]
    count = C.c_long()
    values = C.POINTER(Value)()
    spec = Spec(window, 2)
    res.XResQueryClientIds(connection.display, 1, C.byref(spec), C.byref(count), C.byref(values))
    try:
        return res.XResGetClientPid(values) if values and count.value > 0 else None
    finally:
        if values:
            res.XResClientIdsDestroy(count, values)


def capture(pid,path):
    connection=XWindows()
    pixmap=None;picture=None
    try:
        candidates=[]
        for window,title in connection.windows().items():
            owner=connection.property(window,'_NET_WM_PID')
            if not title:
                continue
            owner_pid = int.from_bytes(owner,'little') if owner else client_pid(connection, window)
            if owner_pid == pid:
                candidates.append(window)
        if not candidates:raise RuntimeError('No window owned by the test process')
        lib=connection.lib
        lib.XGetGeometry.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint)]
        lib.XGetGeometry.restype=C.c_int
        lib.XGetImage.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_ulong,C.c_int];lib.XGetImage.restype=C.POINTER(XImage)
        lib.XDestroyImage.argtypes=[C.POINTER(XImage)];lib.XDestroyImage.restype=C.c_int
        lib.XFreePixmap.argtypes=[C.c_void_p,C.c_ulong];lib.XFreePixmap.restype=C.c_int
        comp=C.CDLL('libXcomposite.so.1');comp.XCompositeNameWindowPixmap.argtypes=[C.c_void_p,C.c_ulong];comp.XCompositeNameWindowPixmap.restype=C.c_ulong
        root=C.c_ulong();x=C.c_int();y=C.c_int();width=C.c_uint();height=C.c_uint();border=C.c_uint();depth=C.c_uint()
        geometries = []
        for window in candidates:
            if lib.XGetGeometry(connection.display,window,C.byref(root),C.byref(x),C.byref(y),C.byref(width),C.byref(height),C.byref(border),C.byref(depth)):
                geometries.append((width.value * height.value, window, width.value, height.value))
        if not geometries:
            raise RuntimeError('Geometry failed')
        _, window, w, h = max(geometries)
        width.value, height.value = w, h
        pixmap=comp.XCompositeNameWindowPixmap(connection.display,window)
        picture=lib.XGetImage(connection.display,pixmap,0,0,width.value,height.value,0xffffffff,2)
        if not picture:raise RuntimeError('XComposite image unavailable')
        frame=picture.contents
        if frame.bits_per_pixel!=32 or frame.byte_order!=0 or frame.red_mask not in (0, 0xff0000):raise RuntimeError(f'Unexpected format {frame.bits_per_pixel} {frame.byte_order} masks {frame.red_mask:x} {frame.green_mask:x} {frame.blue_mask:x}')
        pixels=C.string_at(frame.data,frame.bytes_per_line*frame.height)
        image=Image.frombytes('RGB',(frame.width,frame.height),pixels,'raw','BGRX',frame.bytes_per_line,1)
        image.save(path)
    finally:
        if picture:connection.lib.XDestroyImage(picture)
        if pixmap:connection.lib.XFreePixmap(connection.display,pixmap)
        connection.close()
