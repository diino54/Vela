// Own-process D3D11/Wine integration harness; capture only this process's window.
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <cstdio>
#include <cwchar>
static LRESULT CALLBACK window_proc(HWND w,UINT m,WPARAM p,LPARAM l){if(m==WM_CLOSE){PostQuitMessage(0);return 0;}return DefWindowProcW(w,m,p,l);}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR command,int){
    WNDCLASSW wc={};wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"VelaReShadeD3D11Smoke";RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"Vela ReShade owned integration test",WS_OVERLAPPEDWINDOW,50,50,976,679,nullptr,nullptr,instance,nullptr);
    DXGI_SWAP_CHAIN_DESC desc={};desc.BufferDesc.Width=960;desc.BufferDesc.Height=640;desc.BufferDesc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.SampleDesc.Count=1;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.BufferCount=1;desc.OutputWindow=window;desc.Windowed=TRUE;
    IDXGISwapChain *swap=nullptr;ID3D11Device *device=nullptr;ID3D11DeviceContext *context=nullptr;
    if(FAILED(D3D11CreateDeviceAndSwapChain(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&desc,&swap,&device,nullptr,&context)))return 2;
    ID3D11Texture2D *back=nullptr;swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&back));ID3D11RenderTargetView *rtv=nullptr;device->CreateRenderTargetView(back,nullptr,&rtv);back->Release();ShowWindow(window,SW_SHOW);
    const bool reset_test=std::wcsstr(command,L"--font-reset-check")!=nullptr;
    auto resize=[&](UINT width,UINT height){
        context->OMSetRenderTargets(0,nullptr,nullptr);rtv->Release();rtv=nullptr;
        if(FAILED(swap->ResizeBuffers(1,width,height,DXGI_FORMAT_R8G8B8A8_UNORM,0)))return false;
        ID3D11Texture2D *image=nullptr;swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&image));
        const HRESULT result=device->CreateRenderTargetView(image,nullptr,&rtv);image->Release();return SUCCEEDED(result);
    };
    MSG msg;for(int frame=0;frame<420;++frame){while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)return 0;TranslateMessage(&msg);DispatchMessageW(&msg);}
        if(reset_test && frame==200 && !resize(960,1440))return 3;
        if(reset_test && frame==260 && !resize(960,1080))return 4;
        const float color[4]={.20f,.39f,.30f,1};context->ClearRenderTargetView(rtv,color);swap->Present(0,0);
        if(frame==350){
            ID3D11Texture2D *image=nullptr;swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&image));
            D3D11_TEXTURE2D_DESC rd;image->GetDesc(&rd);rd.Usage=D3D11_USAGE_STAGING;rd.BindFlags=0;rd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;rd.MiscFlags=0;
            ID3D11Texture2D *staging=nullptr;
            if(SUCCEEDED(device->CreateTexture2D(&rd,nullptr,&staging))){context->CopyResource(staging,image);D3D11_MAPPED_SUBRESOURCE mapped;
                if(SUCCEEDED(context->Map(staging,0,D3D11_MAP_READ,0,&mapped))){FILE *f=fopen("owned-frame.ppm","wb");if(f){fprintf(f,"P6\n%u %u\n255\n",rd.Width,rd.Height);for(UINT y=0;y<rd.Height;++y)for(UINT x=0;x<rd.Width;++x)fwrite(static_cast<unsigned char *>(mapped.pData)+y*mapped.RowPitch+x*4,1,3,f);fclose(f);}context->Unmap(staging,0);}staging->Release();
            }image->Release();
        }
        if(frame==150)PostMessageW(window,WM_KEYDOWN,VK_HOME,0);if(frame==151)PostMessageW(window,WM_KEYUP,VK_HOME,0);Sleep(16);
    }
    rtv->Release();context->Release();swap->Release();device->Release();DestroyWindow(window);return 0;
}
