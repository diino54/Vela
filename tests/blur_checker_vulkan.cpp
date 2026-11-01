// Static high-frequency scene for validating backdrop blur, not a benchmark.
#define VK_USE_PLATFORM_XCB_KHR
#include <vulkan/vulkan.h>
#include <xcb/xcb.h>
#include <unistd.h>
#include <signal.h>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#define CHECK(x) do { VkResult r=(x); if(r!=VK_SUCCESS){std::fprintf(stderr,"%s: %d\n",#x,int(r));std::exit(1);} } while(0)
static volatile sig_atomic_t running=1;
static void stop(int){running=0;}
int main(){
 signal(SIGTERM,stop); signal(SIGINT,stop);
 auto* connection=xcb_connect(nullptr,nullptr); if(xcb_connection_has_error(connection)) return 1;
 auto screen=xcb_setup_roots_iterator(xcb_get_setup(connection)).data;
 xcb_window_t window=xcb_generate_id(connection); uint32_t mask=XCB_EVENT_MASK_EXPOSURE|XCB_EVENT_MASK_STRUCTURE_NOTIFY;
 xcb_create_window(connection,XCB_COPY_FROM_PARENT,window,screen->root,0,0,800,450,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,screen->root_visual,XCB_CW_EVENT_MASK,&mask);
 const char title[]="Vela Blur Checker"; xcb_change_property(connection,XCB_PROP_MODE_REPLACE,window,XCB_ATOM_WM_NAME,XCB_ATOM_STRING,8,sizeof(title)-1,title);
 auto cookie=xcb_intern_atom(connection,0,11,"_NET_WM_PID");auto* atom=xcb_intern_atom_reply(connection,cookie,nullptr);uint32_t pid=getpid();
 xcb_change_property(connection,XCB_PROP_MODE_REPLACE,window,atom->atom,XCB_ATOM_CARDINAL,32,1,&pid);free(atom);
 xcb_map_window(connection,window);xcb_flush(connection);
 VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO}; app.pApplicationName=title;app.apiVersion=VK_API_VERSION_1_1;
 const char* extensions[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_XCB_SURFACE_EXTENSION_NAME};
 VkInstanceCreateInfo instance_info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};instance_info.pApplicationInfo=&app;instance_info.enabledExtensionCount=2;instance_info.ppEnabledExtensionNames=extensions;
 VkInstance instance;CHECK(vkCreateInstance(&instance_info,nullptr,&instance));
 VkXcbSurfaceCreateInfoKHR surface_info{VK_STRUCTURE_TYPE_XCB_SURFACE_CREATE_INFO_KHR};surface_info.connection=connection;surface_info.window=window;
 VkSurfaceKHR surface;CHECK(vkCreateXcbSurfaceKHR(instance,&surface_info,nullptr,&surface));
 uint32_t count=0;CHECK(vkEnumeratePhysicalDevices(instance,&count,nullptr));std::vector<VkPhysicalDevice> devices(count);CHECK(vkEnumeratePhysicalDevices(instance,&count,devices.data()));
 VkPhysicalDevice physical=VK_NULL_HANDLE;uint32_t family=0;
 for(auto candidate:devices){uint32_t n=0;vkGetPhysicalDeviceQueueFamilyProperties(candidate,&n,nullptr);std::vector<VkQueueFamilyProperties> props(n);vkGetPhysicalDeviceQueueFamilyProperties(candidate,&n,props.data());
  for(uint32_t i=0;i<n;++i){VkBool32 present=0;vkGetPhysicalDeviceSurfaceSupportKHR(candidate,i,surface,&present);if(present&&(props[i].queueFlags&VK_QUEUE_GRAPHICS_BIT)){physical=candidate;family=i;break;}}
  if(physical)break;
 } if(!physical)return 2;
 float priority=1;VkDeviceQueueCreateInfo queue_info{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};queue_info.queueFamilyIndex=family;queue_info.queueCount=1;queue_info.pQueuePriorities=&priority;
 const char* swap_extension=VK_KHR_SWAPCHAIN_EXTENSION_NAME;VkDeviceCreateInfo device_info{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};device_info.queueCreateInfoCount=1;device_info.pQueueCreateInfos=&queue_info;device_info.enabledExtensionCount=1;device_info.ppEnabledExtensionNames=&swap_extension;
 VkDevice device;CHECK(vkCreateDevice(physical,&device_info,nullptr,&device));VkQueue queue;vkGetDeviceQueue(device,family,0,&queue);
 VkSurfaceCapabilitiesKHR caps;CHECK(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps));
 CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,nullptr));std::vector<VkSurfaceFormatKHR> formats(count);CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,formats.data()));auto format=formats.front();
 for(auto f:formats)if(f.format==VK_FORMAT_B8G8R8A8_UNORM&&f.colorSpace==VK_COLOR_SPACE_SRGB_NONLINEAR_KHR)format=f;
 if(std::getenv("VELA_TEST_10BIT")){
  bool found=false;for(auto f:formats)if((f.format==VK_FORMAT_A2B10G10R10_UNORM_PACK32||f.format==VK_FORMAT_A2R10G10B10_UNORM_PACK32)&&f.colorSpace==VK_COLOR_SPACE_SRGB_NONLINEAR_KHR){format=f;found=true;break;}
  if(!found){std::fprintf(stderr,"10-bit SDR surface unavailable\n");return 3;}
 }
 std::fprintf(stderr,"Checker swapchain format=%d colorspace=%d\n",int(format.format),int(format.colorSpace));
 VkExtent2D extent=caps.currentExtent.width==UINT32_MAX?VkExtent2D{800,450}:caps.currentExtent;
 VkSwapchainCreateInfoKHR swap_info{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};swap_info.surface=surface;swap_info.minImageCount=caps.minImageCount+1;if(caps.maxImageCount)swap_info.minImageCount=std::min(swap_info.minImageCount,caps.maxImageCount);
 swap_info.imageFormat=format.format;swap_info.imageColorSpace=format.colorSpace;swap_info.imageExtent=extent;swap_info.imageArrayLayers=1;swap_info.imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;swap_info.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;swap_info.preTransform=caps.currentTransform;swap_info.compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;swap_info.presentMode=VK_PRESENT_MODE_FIFO_KHR;swap_info.clipped=VK_TRUE;
 VkSwapchainKHR swapchain;CHECK(vkCreateSwapchainKHR(device,&swap_info,nullptr,&swapchain));CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,nullptr));std::vector<VkImage> images(count);CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,images.data()));
 VkAttachmentDescription attachment{};attachment.format=format.format;attachment.samples=VK_SAMPLE_COUNT_1_BIT;attachment.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR;attachment.storeOp=VK_ATTACHMENT_STORE_OP_STORE;attachment.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;attachment.finalLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
 VkAttachmentReference reference{0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};VkSubpassDescription subpass{};subpass.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS;subpass.colorAttachmentCount=1;subpass.pColorAttachments=&reference;
 VkSubpassDependency dependency{};dependency.srcSubpass=VK_SUBPASS_EXTERNAL;dependency.dstSubpass=0;dependency.srcStageMask=dependency.dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;dependency.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
 VkRenderPassCreateInfo pass_info{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};pass_info.attachmentCount=1;pass_info.pAttachments=&attachment;pass_info.subpassCount=1;pass_info.pSubpasses=&subpass;pass_info.dependencyCount=1;pass_info.pDependencies=&dependency;
 VkRenderPass pass;CHECK(vkCreateRenderPass(device,&pass_info,nullptr,&pass));std::vector<VkImageView> views(count);std::vector<VkFramebuffer> framebuffers(count);
 for(uint32_t i=0;i<count;++i){VkImageViewCreateInfo info{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};info.image=images[i];info.viewType=VK_IMAGE_VIEW_TYPE_2D;info.format=format.format;info.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};CHECK(vkCreateImageView(device,&info,nullptr,&views[i]));VkFramebufferCreateInfo fb{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};fb.renderPass=pass;fb.attachmentCount=1;fb.pAttachments=&views[i];fb.width=extent.width;fb.height=extent.height;fb.layers=1;CHECK(vkCreateFramebuffer(device,&fb,nullptr,&framebuffers[i]));}
 VkCommandPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pool_info.queueFamilyIndex=family;pool_info.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;VkCommandPool pool;CHECK(vkCreateCommandPool(device,&pool_info,nullptr,&pool));
 VkCommandBufferAllocateInfo allocate{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};allocate.commandPool=pool;allocate.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;allocate.commandBufferCount=1;VkCommandBuffer command;CHECK(vkAllocateCommandBuffers(device,&allocate,&command));
 VkSemaphoreCreateInfo sem_info{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};VkSemaphore acquired,complete;CHECK(vkCreateSemaphore(device,&sem_info,nullptr,&acquired));CHECK(vkCreateSemaphore(device,&sem_info,nullptr,&complete));
 while(running){while(auto* event=xcb_poll_for_event(connection)){if((event->response_type&127)==XCB_DESTROY_NOTIFY)running=0;free(event);}if(!running)break;
  uint32_t index;VkResult result=vkAcquireNextImageKHR(device,swapchain,UINT64_MAX,acquired,VK_NULL_HANDLE,&index);if(result==VK_ERROR_OUT_OF_DATE_KHR)break;if(result!=VK_SUCCESS&&result!=VK_SUBOPTIMAL_KHR)CHECK(result);
  CHECK(vkResetCommandBuffer(command,0));VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};CHECK(vkBeginCommandBuffer(command,&begin));
  VkClearValue clear{};VkRenderPassBeginInfo render{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};render.renderPass=pass;render.framebuffer=framebuffers[index];render.renderArea.extent=extent;render.clearValueCount=1;render.pClearValues=&clear;vkCmdBeginRenderPass(command,&render,VK_SUBPASS_CONTENTS_INLINE);
  for(int parity=0;parity<2;++parity){std::vector<VkClearRect> rectangles;for(uint32_t y=0;y<extent.height;y+=8)for(uint32_t x=0;x<extent.width;x+=8)if(((x/8+y/8)&1)==unsigned(parity))rectangles.push_back({{{int32_t(x),int32_t(y)},{std::min(8u,extent.width-x),std::min(8u,extent.height-y)}},0,1});
   VkClearAttachment color{};color.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;color.colorAttachment=0;float value=parity?.75f:.15f;color.clearValue.color.float32[0]=color.clearValue.color.float32[1]=color.clearValue.color.float32[2]=value;color.clearValue.color.float32[3]=1;vkCmdClearAttachments(command,1,&color,rectangles.size(),rectangles.data());}
  VkClearAttachment stripe{};stripe.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;stripe.colorAttachment=0;stripe.clearValue.color.float32[0]=stripe.clearValue.color.float32[1]=stripe.clearValue.color.float32[2]=.4f;stripe.clearValue.color.float32[3]=1;
  VkClearRect stripe_rect{{{360,0},{240,extent.height}},0,1};vkCmdClearAttachments(command,1,&stripe,1,&stripe_rect);
  vkCmdEndRenderPass(command);CHECK(vkEndCommandBuffer(command));VkPipelineStageFlags stage=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.waitSemaphoreCount=1;submit.pWaitSemaphores=&acquired;submit.pWaitDstStageMask=&stage;submit.commandBufferCount=1;submit.pCommandBuffers=&command;submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&complete;CHECK(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));
  VkPresentInfoKHR present{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};present.waitSemaphoreCount=1;present.pWaitSemaphores=&complete;present.swapchainCount=1;present.pSwapchains=&swapchain;present.pImageIndices=&index;result=vkQueuePresentKHR(queue,&present);if(result==VK_ERROR_OUT_OF_DATE_KHR)break;CHECK(result);CHECK(vkQueueWaitIdle(queue));std::this_thread::sleep_for(std::chrono::milliseconds(8));
 }
 vkDeviceWaitIdle(device);vkDestroySemaphore(device,acquired,nullptr);vkDestroySemaphore(device,complete,nullptr);vkDestroyCommandPool(device,pool,nullptr);for(uint32_t i=0;i<count;++i){vkDestroyFramebuffer(device,framebuffers[i],nullptr);vkDestroyImageView(device,views[i],nullptr);}vkDestroyRenderPass(device,pass,nullptr);vkDestroySwapchainKHR(device,swapchain,nullptr);vkDestroyDevice(device,nullptr);vkDestroySurfaceKHR(instance,surface,nullptr);vkDestroyInstance(instance,nullptr);xcb_destroy_window(connection,window);xcb_disconnect(connection);return 0;
}
