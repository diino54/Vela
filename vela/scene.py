"""Small animated OpenGL scene, rendered in a separate MangoHud-enabled process."""
import ctypes as C
import math
import os
from pathlib import Path
import sys
import time
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLWindow
from .background import frosted_pixels


class Scene(QOpenGLWindow):
    def __init__(self):
        super().__init__()
        self.setTitle('Vela Preview — starting')
        self.startup_frames = 0
        self.frameSwapped.connect(self.publish_ready)
        self.resize(800, 450)
        self.last_frame = time.monotonic()
        self.animation_time = 0.
        self.paused = False
        self.control_path = os.environ.get('VELA_ANIMATION_CONTROL')
        self.notice_control = os.environ.get('VELA_NOTICE_CONTROL')
        self.notice_opacity = 0.
        self.control_timer = QTimer(self)
        self.control_timer.timeout.connect(self.read_controls)
        self.control_timer.start(16)
        self.read_controls()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(0)

    def read_controls(self):
        if self.control_path:
            try:
                self.paused = Path(self.control_path).read_text() == 'paused'
            except OSError:
                pass
        if self.notice_control:
            try:
                self.notice_opacity = max(0., min(1., float(Path(self.notice_control).read_text())))
            except (OSError, ValueError):
                pass

    def publish_ready(self):
        # Do not let the parent reparent a Qt window before its initial expose,
        # surface creation and swaps have finished. Qt may still recreate or
        # remap that native window during startup.
        self.startup_frames += 1
        if self.startup_frames == 2:
            QTimer.singleShot(100, lambda: self.setTitle('Vela Preview'))

    def initializeGL(self):
        self.gl = C.CDLL('libGL.so.1')
        signatures = {
            'glClearColor': ([C.c_float] * 4, None),
            'glClear': ([C.c_uint], None), 'glEnable': ([C.c_uint], None),
            'glDisable': ([C.c_uint], None), 'glDepthMask': ([C.c_ubyte], None),
            'glGenTextures': ([C.c_int, C.POINTER(C.c_uint)], None),
            'glBindTexture': ([C.c_uint, C.c_uint], None),
            'glTexParameteri': ([C.c_uint, C.c_uint, C.c_int], None),
            'glTexImage2D': ([C.c_uint, C.c_int, C.c_int, C.c_int, C.c_int,
                              C.c_int, C.c_uint, C.c_uint, C.c_void_p], None),
            'glTexCoord2f': ([C.c_float, C.c_float], None),
            'glViewport': ([C.c_int] * 4, None), 'glMatrixMode': ([C.c_uint], None),
            'glLoadIdentity': ([], None), 'glFrustum': ([C.c_double] * 6, None),
            'glTranslatef': ([C.c_float] * 3, None),
            'glRotatef': ([C.c_float] * 4, None), 'glScalef': ([C.c_float] * 3, None),
            'glColor3f': ([C.c_float] * 3, None),
            'glColor4f': ([C.c_float] * 4, None),
            'glBlendFunc': ([C.c_uint, C.c_uint], None),
            'glNormal3f': ([C.c_float] * 3, None), 'glVertex3f': ([C.c_float] * 3, None),
            'glBegin': ([C.c_uint], None), 'glEnd': ([], None),
            'glPushMatrix': ([], None), 'glPopMatrix': ([], None),
            'glLightfv': ([C.c_uint, C.c_uint, C.POINTER(C.c_float)], None),
            'glGenLists': ([C.c_int], C.c_uint), 'glNewList': ([C.c_uint, C.c_uint], None),
            'glEndList': ([], None), 'glCallList': ([C.c_uint], None),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.gl, name)
            function.argtypes, function.restype = args, result
        g = self.gl
        g.glClearColor(27 / 255, 27 / 255, 29 / 255, 1)
        for flag in (0x0B71, 0x0B50, 0x4000, 0x0B57, 0x0BA1, 0x809D):
            g.glEnable(flag)  # Depth, lighting, light 0, color material, normals.
        g.glLightfv(0x4000, 0x1200, (C.c_float * 4)(.25, .25, .25, 1))
        self.create_background()
        self.cube = g.glGenLists(1)
        g.glNewList(self.cube, 0x1300)
        faces = (
            ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), (.18, .44, .82)),
            ((0, 0, -1), ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)), (.46, .49, .54)),
            ((1, 0, 0), ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)), (.42, .46, .52)),
            ((-1, 0, 0), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)), (.18, .44, .82)),
            ((0, 1, 0), ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)), (.65, .68, .72)),
            ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)), (.38, .41, .46)),
        )
        # Subdivide the six faces and project their edge bands onto a rounded
        # box. Shared analytic normals keep the bevels smooth at face seams.
        radius = .12
        inner = 1 - radius
        steps = [-1 + radius * i / 8 for i in range(9)]
        steps += [inner + radius * i / 8 for i in range(9)]
        steps += [-inner + 2 * inner * i / 16 for i in range(17)]
        steps = sorted(set(steps))

        def vertex(normal, vertices, u, v):
            u, v = (u + 1) / 2, (v + 1) / 2
            point = tuple((1-u)*(1-v)*vertices[0][k] + u*(1-v)*vertices[1][k]
                          + u*v*vertices[2][k] + (1-u)*v*vertices[3][k] for k in range(3))
            nearest = tuple(max(-inner, min(inner, x)) for x in point)
            delta = tuple(x - y for x, y in zip(point, nearest))
            length = math.sqrt(sum(x*x for x in delta))
            n = tuple(x / length for x in delta)
            position = tuple(nearest[k] + radius*n[k] for k in range(3))
            # One continuous vertical gradient across the complete object,
            # independent of face boundaries and rounded corner normals.
            blend = max(0., min(1., (position[1] + 1.) * .5))
            stops = ((.035, .075, .22), (.12, .39, .88), (.48, .79, 1.))
            lower, upper = (stops[0], stops[1]) if blend < .5 else (stops[1], stops[2])
            amount = blend * 2 if blend < .5 else (blend - .5) * 2
            g.glColor3f(*(a + (b - a) * amount for a, b in zip(lower, upper)))
            g.glNormal3f(*n)
            g.glVertex3f(*position)

        g.glBegin(0x0007)
        for normal, vertices, _ in faces:
            for u0, u1 in zip(steps, steps[1:]):
                for v0, v1 in zip(steps, steps[1:]):
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
                        vertex(normal, vertices, u, v)
        g.glEnd()
        g.glEndList()

    def create_background(self):
        """Bake a softly blurred grid once; no per-frame blur or desktop capture."""
        width, height = 1024, 576
        pixels = bytearray(frosted_pixels(width, height))
        g = self.gl
        self.background_texture = C.c_uint()
        g.glGenTextures(1, C.byref(self.background_texture))
        g.glBindTexture(0x0DE1, self.background_texture.value)
        for parameter in (0x2800, 0x2801):
            g.glTexParameteri(0x0DE1, parameter, 0x2601)
        for parameter in (0x2802, 0x2803):
            g.glTexParameteri(0x0DE1, parameter, 0x812F)
        data = (C.c_ubyte * len(pixels)).from_buffer(pixels)
        g.glTexImage2D(0x0DE1, 0, 0x1907, width, height, 0, 0x1907, 0x1401, data)

    def draw_background(self):
        g = self.gl
        g.glDisable(0x0B50)
        g.glDisable(0x0B71)
        g.glDepthMask(0)
        g.glMatrixMode(0x1701)
        g.glLoadIdentity()
        g.glMatrixMode(0x1700)
        g.glLoadIdentity()
        g.glEnable(0x0DE1)
        g.glBindTexture(0x0DE1, self.background_texture.value)
        g.glColor3f(1, 1, 1)
        g.glBegin(0x0007)
        for u, v, x, y in ((0, 0, -1, -1), (1, 0, 1, -1),
                            (1, 1, 1, 1), (0, 1, -1, 1)):
            g.glTexCoord2f(u, v)
            g.glVertex3f(x, y, 0)
        g.glEnd()
        g.glDisable(0x0DE1)
        g.glDepthMask(1)
        g.glEnable(0x0B71)
        g.glEnable(0x0B50)

    def paintGL(self):
        g = self.gl
        now = time.monotonic()
        if not self.paused:
            self.animation_time += now - self.last_frame
        self.last_frame = now
        t = self.animation_time
        scale = self.devicePixelRatio()
        g.glViewport(0, 0, round(self.width() * scale), round(self.height() * scale))
        g.glClear(0x4000 | 0x0100)
        self.draw_background()
        g.glMatrixMode(0x1701)
        g.glLoadIdentity()
        aspect = self.width() / max(1, self.height())
        g.glFrustum(-.045 * aspect, .045 * aspect, -.045, .045, .1, 30)
        g.glMatrixMode(0x1700)
        g.glLoadIdentity()
        g.glLightfv(0x4000, 0x1203, (C.c_float * 4)(-3, 4, 5, 1))
        # A gentle orbit gives the preview a clear sense of motion without
        # moving the object behind the overlay in the upper corner.
        g.glTranslatef(.35 + .10 * math.sin(t * .65), -.28 + .08 * math.sin(t * 1.1),
                       -5.4 + .05 * math.sin(t * .45))
        g.glRotatef(24 + t * 12, 1, 0, 0)
        g.glRotatef(t * 28, 0, 1, 0)
        g.glScalef(.58, .58, .58)
        g.glCallList(self.cube)
        self.draw_notice_veil()

    def draw_notice_veil(self):
        if self.notice_opacity <= 0:
            return
        g = self.gl
        g.glDisable(0x0B50)  # Lighting
        g.glDisable(0x0B71)  # Depth test
        g.glEnable(0x0BE2)  # Blending
        g.glBlendFunc(0x0302, 0x0303)  # SRC_ALPHA, ONE_MINUS_SRC_ALPHA
        g.glMatrixMode(0x1701)
        g.glPushMatrix()
        g.glLoadIdentity()
        g.glMatrixMode(0x1700)
        g.glPushMatrix()
        g.glLoadIdentity()
        g.glColor4f(0, 0, 0, .25 * self.notice_opacity)
        g.glBegin(0x0007)
        for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            g.glVertex3f(x, y, 0)
        g.glEnd()
        g.glPopMatrix()
        g.glMatrixMode(0x1701)
        g.glPopMatrix()
        g.glMatrixMode(0x1700)
        g.glDisable(0x0BE2)
        g.glEnable(0x0B71)
        g.glEnable(0x0B50)


def main():
    surface = QSurfaceFormat()
    surface.setVersion(2, 1)
    surface.setProfile(QSurfaceFormat.CompatibilityProfile)
    surface.setDepthBufferSize(24)
    surface.setSamples(4)
    surface.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(surface)
    app = QGuiApplication(sys.argv)
    scene = Scene()
    scene.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
