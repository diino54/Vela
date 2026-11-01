// Own-process GPU integration harness. Never captures another application's surface.
#include <windows.h>
#include <d3d11_1.h>
#include <dxgi1_4.h>
#include <cstdio>
#include <cwchar>
#include <cmath>
#include <cstdint>

static LRESULT CALLBACK window_proc(HWND w, UINT m, WPARAM p, LPARAM l) {
    if (m == WM_CLOSE) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(w,m,p,l);
}
#include "smoke_pixels.hpp"
static void export_frame(IDXGISwapChain *swap,ID3D11Device *device,ID3D11DeviceContext *context,const char *name,int hdr) {
    ID3D11Texture2D *image=nullptr;
    if(FAILED(swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&image))))return;
    D3D11_TEXTURE2D_DESC desc;image->GetDesc(&desc);desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
    ID3D11Texture2D *staging=nullptr;
    if(SUCCEEDED(device->CreateTexture2D(&desc,nullptr,&staging))) {
        context->CopyResource(staging,image);D3D11_MAPPED_SUBRESOURCE mapped;
        if(SUCCEEDED(context->Map(staging,0,D3D11_MAP_READ,0,&mapped))) {
            save_pixels(name,mapped.pData,mapped.RowPitch,desc.Width,desc.Height,hdr);context->Unmap(staging,0);
        }
        staging->Release();
    }
    image->Release();
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR command,int) {
    const bool visual=std::wcsstr(command,L"--visual-check")!=nullptr;
    const bool reset=std::wcsstr(command,L"--font-reset-check")!=nullptr;
    const int hdr=std::wcsstr(command,L"--hdr-scrgb")?1:std::wcsstr(command,L"--hdr-pq")?2:0;
    WNDCLASSW wc={};wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"VelaReShadeD3D11Smoke";RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"Vela ReShade owned integration test",WS_OVERLAPPEDWINDOW,50,50,976,679,nullptr,nullptr,instance,nullptr);
    const DXGI_FORMAT format=hdr==1?DXGI_FORMAT_R16G16B16A16_FLOAT:hdr==2?DXGI_FORMAT_R10G10B10A2_UNORM:DXGI_FORMAT_R8G8B8A8_UNORM;
    DXGI_SWAP_CHAIN_DESC desc={};desc.BufferDesc.Width=960;desc.BufferDesc.Height=640;desc.BufferDesc.Format=format;desc.SampleDesc.Count=1;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.BufferCount=hdr?2:1;desc.OutputWindow=window;desc.Windowed=TRUE;desc.SwapEffect=hdr?DXGI_SWAP_EFFECT_FLIP_DISCARD:DXGI_SWAP_EFFECT_DISCARD;
    IDXGISwapChain *swap=nullptr;ID3D11Device *device=nullptr;ID3D11DeviceContext *context=nullptr;
    if(FAILED(D3D11CreateDeviceAndSwapChain(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&desc,&swap,&device,nullptr,&context)))return 2;
    if(hdr) {
        IDXGISwapChain3 *modern=nullptr;
        if(FAILED(swap->QueryInterface(__uuidof(IDXGISwapChain3),reinterpret_cast<void **>(&modern))))return 5;
        const HRESULT result=modern->SetColorSpace1(hdr==1?DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709:DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);
        modern->Release();if(FAILED(result))return 6;
    }
    ID3D11DeviceContext1 *context1=nullptr;context->QueryInterface(__uuidof(ID3D11DeviceContext1),reinterpret_cast<void **>(&context1));
    ID3D11Texture2D *back=nullptr;swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&back));ID3D11RenderTargetView *rtv=nullptr;device->CreateRenderTargetView(back,nullptr,&rtv);back->Release();ShowWindow(window,SW_SHOW);
    UINT width=960,height=640;
    auto resize=[&](UINT w,UINT h) {
        context->OMSetRenderTargets(0,nullptr,nullptr);rtv->Release();rtv=nullptr;
        if(FAILED(swap->ResizeBuffers(hdr?2:1,w,h,format,0)))return false;
        width=w;height=h;ID3D11Texture2D *image=nullptr;swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void **>(&image));
        const HRESULT result=device->CreateRenderTargetView(image,nullptr,&rtv);image->Release();return SUCCEEDED(result);
    };
    MSG msg;
    for(int frame=0;frame<420;++frame) {
        while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)return 0;TranslateMessage(&msg);DispatchMessageW(&msg);}
        if(reset&&frame==200&&!resize(960,1440))return 3;
        if(reset&&frame==260&&!resize(960,1080))return 4;
        const float base[4]={.2f,.39f,.3f,1};context->ClearRenderTargetView(rtv,base);
        if(context1)for(UINT y=0;y<height;y+=24)for(UINT x=0;x<width;x+=24) {
            const bool bright=((x/24+y/24)%2)!=0;
            const float value=hdr==1?(bright?4.f:.1f):hdr==2?pq_encode((bright?320.f:8.f)/10000.f):(bright?.9f:.03f);
            const float color[4]={value,value,value,1};D3D11_RECT rect={static_cast<LONG>(x),static_cast<LONG>(y),static_cast<LONG>(x+24>width?width:x+24),static_cast<LONG>(y+24>height?height:y+24)};
            context1->ClearView(rtv,color,&rect,1);
        }
        swap->Present(0,0);
        if(visual&&(frame==149||frame==153||frame==160||frame==180||frame==302||frame==310||frame==330)) {
            char name[64];std::snprintf(name,sizeof(name),"visual-%d",frame);export_frame(swap,device,context,name,hdr);
        }
        if(frame==350)export_frame(swap,device,context,"owned-frame",hdr);
        if(frame==150||(visual&&frame==300))PostMessageW(window,WM_KEYDOWN,VK_HOME,0);
        if(frame==151||(visual&&frame==301))PostMessageW(window,WM_KEYUP,VK_HOME,0);
        Sleep(16);
    }
    if(context1)context1->Release();rtv->Release();context->Release();swap->Release();device->Release();DestroyWindow(window);return 0;
}
