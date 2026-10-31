"""Static OpenGL checkerboard for blur validation, including MSAA resolve."""
import ctypes as C
import sys
import os
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication,QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLWindow

class Checker(QOpenGLWindow):
    def __init__(self):
        super().__init__();self.setTitle('Vela Blur Checker');self.resize(800,450)
        self.timer=QTimer(self);self.timer.timeout.connect(self.update);self.timer.start(16)
    def initializeGL(self):
        self.gl=C.CDLL('libGL.so.1')
        self.gl.glGetString.argtypes=[C.c_uint];self.gl.glGetString.restype=C.c_char_p
        self.gl.glGetError.restype=C.c_uint
        print('Checker GL:',self.gl.glGetString(0x1F02),flush=True)
        signatures={'glViewport':([C.c_int]*4,None),'glClear':([C.c_uint],None),
         'glClearColor':([C.c_float]*4,None),'glDisable':([C.c_uint],None),'glEnable':([C.c_uint],None),
         'glMatrixMode':([C.c_uint],None),'glLoadIdentity':([],None),'glOrtho':([C.c_double]*6,None),
         'glGenLists':([C.c_int],C.c_uint),'glNewList':([C.c_uint,C.c_uint],None),'glEndList':([],None),
         'glCallList':([C.c_uint],None),'glBegin':([C.c_uint],None),'glEnd':([],None),
         'glVertex2f':([C.c_float,C.c_float],None),'glColor3f':([C.c_float]*3,None)}
        for name,(args,result) in signatures.items():
            f=getattr(self.gl,name);f.argtypes=args;f.restype=result
        self.display_list=0;self.dimensions=None
    def paintGL(self):
        g=self.gl;w=round(self.width()*self.devicePixelRatio());h=round(self.height()*self.devicePixelRatio())
        g.glViewport(0,0,w,h);g.glDisable(0x0C11);g.glDisable(0x0BE2);g.glDisable(0x0B71);g.glDisable(0x0DE1)
        g.glEnable(0x8DB9) if os.environ.get('VELA_TEST_SRGB') else g.glDisable(0x8DB9)
        g.glClearColor(.15,.15,.15,1);g.glClear(0x4000)
        g.glMatrixMode(0x1701);g.glLoadIdentity();g.glOrtho(0,w,0,h,-1,1)
        g.glMatrixMode(0x1700);g.glLoadIdentity()
        if self.dimensions!=(w,h):
            self.display_list=g.glGenLists(1);g.glNewList(self.display_list,0x1300);g.glBegin(0x0007)
            for y in range(0,h,8):
                for x in range(0,w,8):
                    value=.4 if 360<=x<600 else (.75 if (x//8+y//8)%2 else .15);g.glColor3f(value,value,value)
                    for px,py in ((x,y),(x+8,y),(x+8,y+8),(x,y+8)):g.glVertex2f(px,py)
            g.glEnd();g.glEndList();self.dimensions=(w,h)
        g.glCallList(self.display_list)
        error=g.glGetError()
        if error: print('Checker GL error',hex(error),flush=True)

if __name__=='__main__':
    surface=QSurfaceFormat();surface.setVersion(2,1);surface.setProfile(QSurfaceFormat.CompatibilityProfile);surface.setSamples(4);surface.setSwapInterval(0);QSurfaceFormat.setDefaultFormat(surface)
    app=QGuiApplication(sys.argv);window=Checker();window.show();sys.exit(app.exec())
