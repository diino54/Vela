// Own-process OpenGL/Wine integration harness. Never captures other windows.
#include <windows.h>
#include <gl/GL.h>
#include <cstdio>
#include <vector>
static LRESULT CALLBACK window_proc(HWND w,UINT m,WPARAM p,LPARAM l) {
    if(m==WM_CLOSE){PostQuitMessage(0);return 0;}return DefWindowProcW(w,m,p,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int)
{
    WNDCLASSW wc={};wc.style=CS_OWNDC;wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"VelaReShadeSmoke";
    RegisterClassW(&wc);HWND window=CreateWindowW(wc.lpszClassName,L"Vela ReShade owned integration test",WS_OVERLAPPEDWINDOW,50,50,976,679,nullptr,nullptr,instance,nullptr);
    HDC dc=GetDC(window);PIXELFORMATDESCRIPTOR pfd={};pfd.nSize=sizeof(pfd);pfd.nVersion=1;pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=32;
    SetPixelFormat(dc,ChoosePixelFormat(dc,&pfd),&pfd);HGLRC context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context))return 2;
    ShowWindow(window,SW_SHOW);MSG msg;
    for(int frame=0;frame<420;++frame){
        while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)return 0;TranslateMessage(&msg);DispatchMessageW(&msg);}
        RECT rc;GetClientRect(window,&rc);const int width=rc.right,height=rc.bottom;glViewport(0,0,width,height);
        glEnable(GL_SCISSOR_TEST);for(int y=0;y<height;y+=40)for(int x=0;x<width;x+=40){bool a=((x+y)/40)%2;glScissor(x,y,40,40);glClearColor(a?.18f:.25f,a?.32f:.42f,a?.25f:.34f,1);glClear(GL_COLOR_BUFFER_BIT);}glDisable(GL_SCISSOR_TEST);
        SwapBuffers(dc);
        if(frame==150)PostMessageW(window,WM_KEYDOWN,VK_HOME,0);
        if(frame==151)PostMessageW(window,WM_KEYUP,VK_HOME,0);
        if(frame==350){
            std::vector<unsigned char> pixels(width*height*3);glReadBuffer(GL_FRONT);glPixelStorei(GL_PACK_ALIGNMENT,1);glReadPixels(0,0,width,height,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
            FILE *file=fopen("owned-frame.ppm","wb");if(file){fprintf(file,"P6\n%d %d\n255\n",width,height);for(int y=height-1;y>=0;--y)fwrite(pixels.data()+y*width*3,1,width*3,file);fclose(file);}
        }
        Sleep(16);
    }
    wglMakeCurrent(nullptr,nullptr);wglDeleteContext(context);ReleaseDC(window,dc);DestroyWindow(window);return 0;
}
