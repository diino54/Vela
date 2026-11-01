// Own-process D3D12/VKD3D test. Only its own backbuffer is read back.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <cwchar>
#include "smoke_pixels.hpp"
static LRESULT CALLBACK proc(HWND w,UINT m,WPARAM p,LPARAM l){if(m==WM_CLOSE){PostQuitMessage(0);return 0;}return DefWindowProcW(w,m,p,l);}
static D3D12_RESOURCE_BARRIER barrier(ID3D12Resource *image,D3D12_RESOURCE_STATES from,D3D12_RESOURCE_STATES to){D3D12_RESOURCE_BARRIER b={};b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;b.Transition.pResource=image;b.Transition.StateBefore=from;b.Transition.StateAfter=to;b.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;return b;}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR command,int){
    const bool visual=std::wcsstr(command,L"--visual-check")!=nullptr;
    const int hdr=std::wcsstr(command,L"--hdr-scrgb")?1:std::wcsstr(command,L"--hdr-pq")?2:0;
    WNDCLASSW wc={};wc.lpfnWndProc=proc;wc.hInstance=instance;wc.lpszClassName=L"VelaD3D12OwnedTest";RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"Vela ReShade owned integration test",WS_OVERLAPPEDWINDOW,50,50,976,679,nullptr,nullptr,instance,nullptr);
    ID3D12Device *device=nullptr;if(FAILED(D3D12CreateDevice(nullptr,D3D_FEATURE_LEVEL_11_0,__uuidof(ID3D12Device),reinterpret_cast<void **>(&device))))return 2;
    D3D12_COMMAND_QUEUE_DESC qd={};qd.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;ID3D12CommandQueue *queue=nullptr;if(FAILED(device->CreateCommandQueue(&qd,__uuidof(ID3D12CommandQueue),reinterpret_cast<void **>(&queue))))return 3;
    IDXGIFactory2 *factory=nullptr;CreateDXGIFactory1(__uuidof(IDXGIFactory2),reinterpret_cast<void **>(&factory));
    DXGI_SWAP_CHAIN_DESC1 sd={};sd.Width=960;sd.Height=640;sd.BufferCount=2;sd.Format=hdr==1?DXGI_FORMAT_R16G16B16A16_FLOAT:hdr==2?DXGI_FORMAT_R10G10B10A2_UNORM:DXGI_FORMAT_R8G8B8A8_UNORM;sd.SampleDesc.Count=1;sd.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;sd.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;
    IDXGISwapChain1 *base=nullptr;if(FAILED(factory->CreateSwapChainForHwnd(queue,window,&sd,nullptr,nullptr,&base)))return 4;
    IDXGISwapChain3 *swap=nullptr;base->QueryInterface(__uuidof(IDXGISwapChain3),reinterpret_cast<void **>(&swap));base->Release();factory->Release();
    if(hdr&&FAILED(swap->SetColorSpace1(hdr==1?DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709:DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020)))return 5;
    D3D12_DESCRIPTOR_HEAP_DESC hd={};hd.NumDescriptors=2;hd.Type=D3D12_DESCRIPTOR_HEAP_TYPE_RTV;ID3D12DescriptorHeap *heap=nullptr;device->CreateDescriptorHeap(&hd,__uuidof(ID3D12DescriptorHeap),reinterpret_cast<void **>(&heap));
    ID3D12Resource *images[2]={};D3D12_CPU_DESCRIPTOR_HANDLE views[2];UINT step=device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
    for(UINT i=0;i<2;++i){swap->GetBuffer(i,__uuidof(ID3D12Resource),reinterpret_cast<void **>(&images[i]));views[i]=heap->GetCPUDescriptorHandleForHeapStart();views[i].ptr+=i*step;device->CreateRenderTargetView(images[i],nullptr,views[i]);}
    ID3D12CommandAllocator *allocator=nullptr;device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,__uuidof(ID3D12CommandAllocator),reinterpret_cast<void **>(&allocator));
    ID3D12GraphicsCommandList *list=nullptr;device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,allocator,nullptr,__uuidof(ID3D12GraphicsCommandList),reinterpret_cast<void **>(&list));list->Close();
    ID3D12Fence *fence=nullptr;device->CreateFence(0,D3D12_FENCE_FLAG_NONE,__uuidof(ID3D12Fence),reinterpret_cast<void **>(&fence));HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);UINT64 serial=0;
    auto wait=[&](){queue->Signal(fence,++serial);if(fence->GetCompletedValue()<serial){fence->SetEventOnCompletion(serial,event);WaitForSingleObject(event,10000);}};
    auto export_frame=[&](ID3D12Resource *image,const char *name){
        auto desc=image->GetDesc();D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint;UINT rows;UINT64 rowbytes,total;device->GetCopyableFootprints(&desc,0,1,0,&footprint,&rows,&rowbytes,&total);
        D3D12_HEAP_PROPERTIES hp={};hp.Type=D3D12_HEAP_TYPE_READBACK;D3D12_RESOURCE_DESC rd={};rd.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;rd.Width=total;rd.Height=1;rd.DepthOrArraySize=1;rd.MipLevels=1;rd.SampleDesc.Count=1;rd.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        ID3D12Resource *readback=nullptr;if(FAILED(device->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&rd,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,__uuidof(ID3D12Resource),reinterpret_cast<void **>(&readback))))return;
        allocator->Reset();list->Reset(allocator,nullptr);auto b=barrier(image,D3D12_RESOURCE_STATE_PRESENT,D3D12_RESOURCE_STATE_COPY_SOURCE);list->ResourceBarrier(1,&b);
        D3D12_TEXTURE_COPY_LOCATION from={};from.pResource=image;from.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        D3D12_TEXTURE_COPY_LOCATION to={};to.pResource=readback;to.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;to.PlacedFootprint=footprint;list->CopyTextureRegion(&to,0,0,0,&from,nullptr);
        b=barrier(image,D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_PRESENT);list->ResourceBarrier(1,&b);list->Close();ID3D12CommandList *commands[]={list};queue->ExecuteCommandLists(1,commands);wait();
        void *data=nullptr;D3D12_RANGE range={0,static_cast<SIZE_T>(total)};if(SUCCEEDED(readback->Map(0,&range,&data))){save_pixels(name,data,footprint.Footprint.RowPitch,sd.Width,sd.Height,hdr);readback->Unmap(0,nullptr);}readback->Release();
    };
    ShowWindow(window,SW_SHOW);MSG msg;
    for(int frame=0;frame<420;++frame){
        while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)return 0;TranslateMessage(&msg);DispatchMessageW(&msg);}
        UINT index=swap->GetCurrentBackBufferIndex();allocator->Reset();list->Reset(allocator,nullptr);auto b=barrier(images[index],D3D12_RESOURCE_STATE_PRESENT,D3D12_RESOURCE_STATE_RENDER_TARGET);list->ResourceBarrier(1,&b);
        for(UINT y=0;y<sd.Height;y+=24)for(UINT x=0;x<sd.Width;x+=24){bool bright=((x/24+y/24)%2)!=0;float v=hdr==1?(bright?4.f:.1f):hdr==2?pq_encode((bright?320.f:8.f)/10000.f):(bright?.9f:.03f);float color[4]={v,v,v,1};D3D12_RECT rect={static_cast<LONG>(x),static_cast<LONG>(y),static_cast<LONG>(x+24>sd.Width?sd.Width:x+24),static_cast<LONG>(y+24>sd.Height?sd.Height:y+24)};list->ClearRenderTargetView(views[index],color,1,&rect);}
        b=barrier(images[index],D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_PRESENT);list->ResourceBarrier(1,&b);list->Close();ID3D12CommandList *commands[]={list};queue->ExecuteCommandLists(1,commands);swap->Present(0,0);wait();
        if(visual&&(frame==149||frame==153||frame==160||frame==180||frame==302||frame==310||frame==330)){char name[64];std::snprintf(name,sizeof(name),"visual-%d",frame);export_frame(images[index],name);}
        if(frame==350)export_frame(images[index],"owned-frame");
        if(frame==150||(visual&&frame==300))PostMessageW(window,WM_KEYDOWN,VK_HOME,0);if(frame==151||(visual&&frame==301))PostMessageW(window,WM_KEYUP,VK_HOME,0);Sleep(16);
    }
    wait();CloseHandle(event);fence->Release();list->Release();allocator->Release();for(auto *image:images)image->Release();heap->Release();swap->Release();queue->Release();device->Release();DestroyWindow(window);return 0;
}
