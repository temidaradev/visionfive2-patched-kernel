#define _GNU_SOURCE
#include <gbm.h>
#include <xf86drmMode.h>
#include <xf86drm.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

struct gbm_device *gbm_create_device(int fd)
{
    static struct gbm_device *(*real)(int);
    static int released=0;
    if (!real) real=dlsym(RTLD_NEXT,"gbm_create_device");
    struct gbm_device *device=real(fd);
    int master=drmIsMaster(fd);
    fprintf(stderr,"VF2_GBM device fd=%d device=%p master=%d\n",fd,device,master);
    if (!released && getenv("VF2_DROP_RENDER_MASTER")) {
        drmVersionPtr v=drmGetVersion(fd);
        if (v && v->name && strcmp(v->name,"starfive")==0) {
            released=1;
            if (master) {
                int r=drmDropMaster(fd);
                fprintf(stderr,"VF2_DRM drop-render-master fd=%d ret=%d errno=%d\n",fd,r,errno);
            }
        }
        if(v) drmFreeVersion(v);
    }
    return device;
}

extern __eglMustCastToProperFunctionPointerType (*epoxy_eglGetProcAddress)(const char*);
extern unsigned (*epoxy_glCheckFramebufferStatus)(unsigned);
static __eglMustCastToProperFunctionPointerType (*real_proc)(const char*);
static PFNEGLQUERYDMABUFFORMATSEXTPROC real_formats;
static PFNEGLQUERYDMABUFMODIFIERSEXTPROC real_modifiers;
static PFNEGLCREATEIMAGEKHRPROC real_image;
static unsigned (*real_fbo)(unsigned);
static struct wl_display *server_wayland;
static EGLDisplay server_egl=EGL_NO_DISPLAY;
static int server_bound;
static void bind_legacy_drm(void)
{
    if(!getenv("VF2_BIND_WL_DRM") || server_bound || !server_wayland || server_egl==EGL_NO_DISPLAY || !real_proc) return;
    PFNEGLBINDWAYLANDDISPLAYWLPROC bind=(void*)real_proc("eglBindWaylandDisplayWL");
    if(bind) {
        EGLBoolean r=bind(server_egl,server_wayland);
        fprintf(stderr,"VF2_WL bind EGL display=%p Wayland display=%p ret=%d\n",server_egl,server_wayland,r);
        server_bound=r;
    }
}
struct wl_display *wl_display_create(void)
{
    static struct wl_display *(*real)(void);
    if(!real) real=dlsym(RTLD_NEXT,"wl_display_create");
    struct wl_display *d=real();
    if(getenv("VF2_BIND_WL_DRM")) { server_wayland=d; bind_legacy_drm(); }
    return d;
}
static void unbind_legacy_drm(void)
{
    if(server_bound && real_proc) {
        PFNEGLUNBINDWAYLANDDISPLAYWLPROC unbind=(void*)real_proc("eglUnbindWaylandDisplayWL");
        if(unbind) unbind(server_egl,server_wayland);
        server_bound=0;
    }
}
void wl_display_destroy(struct wl_display *d)
{
    static void (*real)(struct wl_display*);
    if(!real) real=dlsym(RTLD_NEXT,"wl_display_destroy");
    if(d==server_wayland) { unbind_legacy_drm(); server_wayland=NULL; }
    real(d);
}
extern EGLBoolean (*epoxy_eglTerminate)(EGLDisplay);
static EGLBoolean (*real_terminate)(EGLDisplay);
static EGLBoolean terminate_egl(EGLDisplay d)
{
    if(d==server_egl) { unbind_legacy_drm(); server_egl=EGL_NO_DISPLAY; }
    return real_terminate(d);
}

static EGLBoolean query_formats(EGLDisplay d,EGLint max,EGLint *formats,EGLint *count)
{
    EGLBoolean r=real_formats(d,max,formats,count);
    if(r && getenv("VF2_BIND_WL_DRM") && server_egl==EGL_NO_DISPLAY) { server_egl=d; bind_legacy_drm(); }
    fprintf(stderr,"VF2_EGL formats display=%p max=%d ret=%d count=%d values=",d,max,r,count?*count:-1);
    if(r && formats && count) for(int i=0;i<*count && i<max;i++) fprintf(stderr,"%08x,",formats[i]);
    fputc('\n',stderr); return r;
}
static EGLBoolean query_modifiers(EGLDisplay d,EGLint format,EGLint max,EGLuint64KHR *mods,EGLBoolean *external,EGLint *count)
{
    EGLBoolean r=real_modifiers(d,format,max,mods,external,count);
    if(max && (format==0x34325258 || format==0x34325241)) {
        fprintf(stderr,"VF2_EGL modifiers display=%p format=%08x ret=%d count=%d values=",d,format,r,count?*count:-1);
        if(r && mods && count) for(int i=0;i<*count && i<max;i++) fprintf(stderr,"%llx/ext%d,",(unsigned long long)mods[i],external?external[i]:-1);
        fputc('\n',stderr);
    }
    return r;
}
static EGLImageKHR create_image(EGLDisplay d,EGLContext ctx,EGLenum target,EGLClientBuffer buffer,const EGLint *attrs)
{
    EGLImageKHR image=real_image(d,ctx,target,buffer,attrs);
    fprintf(stderr,"VF2_EGL image display=%p target=%x image=%p attrs=",d,target,image);
    if(attrs) for(int i=0;i<60 && attrs[i]!=EGL_NONE;i+=2) fprintf(stderr,"%x:%x,",attrs[i],attrs[i+1]);
    fputc('\n',stderr); return image;
}
static __eglMustCastToProperFunctionPointerType get_proc(const char *name)
{
    __eglMustCastToProperFunctionPointerType p=real_proc(name);
    if(epoxy_eglGetProcAddress!=get_proc) real_proc=epoxy_eglGetProcAddress;
    epoxy_eglGetProcAddress=get_proc;
    if(!strcmp(name,"eglQueryDmaBufFormatsEXT")) { real_formats=(void*)p; return (void*)query_formats; }
    if(!strcmp(name,"eglQueryDmaBufModifiersEXT")) { real_modifiers=(void*)p; return (void*)query_modifiers; }
    if(!strcmp(name,"eglCreateImageKHR")) { real_image=(void*)p; return (void*)create_image; }
    return p;
}
static unsigned check_fbo(unsigned target)
{
    unsigned status=real_fbo(target);
    if(epoxy_glCheckFramebufferStatus!=check_fbo) real_fbo=epoxy_glCheckFramebufferStatus;
    epoxy_glCheckFramebufferStatus=check_fbo;
    fprintf(stderr,"VF2_GL framebuffer target=%x status=%x\n",target,status);
    return status;
}
__attribute__((constructor)) static void trace_egl(void)
{
    // Call GLVND directly: calling libepoxy's initial resolver after replacing
    // its dispatch pointer would recurse through our own hook.
    real_proc=dlsym(RTLD_NEXT,"eglGetProcAddress");
    if(real_proc) epoxy_eglGetProcAddress=get_proc;
    real_terminate=dlsym(RTLD_NEXT,"eglTerminate");
    if(real_terminate) epoxy_eglTerminate=terminate_egl;
}

struct gbm_bo *gbm_bo_create(struct gbm_device *d, uint32_t w, uint32_t h, uint32_t f, uint32_t flags)
{
    static struct gbm_bo *(*real)(struct gbm_device*,uint32_t,uint32_t,uint32_t,uint32_t);
    if (!real) real=dlsym(RTLD_NEXT,"gbm_bo_create");
    struct gbm_bo *bo=real(d,w,h,f,flags); int e=errno;
    fprintf(stderr,"VF2_GBM create fd=%d size=%ux%u format=%08x flags=%08x bo=%p errno=%d\n",gbm_device_get_fd(d),w,h,f,flags,bo,e);
    errno=e; return bo;
}
struct gbm_bo *gbm_bo_create_with_modifiers(struct gbm_device *d,uint32_t w,uint32_t h,uint32_t f,const uint64_t *mods,const unsigned count)
{
    static struct gbm_bo *(*real)(struct gbm_device*,uint32_t,uint32_t,uint32_t,const uint64_t*,unsigned);
    if (!real) real=dlsym(RTLD_NEXT,"gbm_bo_create_with_modifiers");
    struct gbm_bo *bo=real(d,w,h,f,mods,count); int e=errno;
    fprintf(stderr,"VF2_GBM modifiers fd=%d size=%ux%u format=%08x count=%u bo=%p errno=%d mods=",gbm_device_get_fd(d),w,h,f,count,bo,e);
    for(unsigned i=0;i<count;i++) fprintf(stderr,"%llx,",(unsigned long long)mods[i]);
    fputc('\n',stderr); errno=e; return bo;
}
int gbm_bo_get_fd_for_plane(struct gbm_bo *bo,int plane)
{
    static int (*real)(struct gbm_bo*,int);
    if (!real) real=dlsym(RTLD_NEXT,"gbm_bo_get_fd_for_plane");
    int fd=real(bo,plane),e=errno;
    fprintf(stderr,"VF2_GBM export bo=%p plane=%d fd=%d stride=%u modifier=%llx errno=%d\n",bo,plane,fd,gbm_bo_get_stride_for_plane(bo,plane),(unsigned long long)gbm_bo_get_modifier(bo),e);
    errno=e; return fd;
}
int drmModeAddFB2(int fd,uint32_t w,uint32_t h,uint32_t format,const uint32_t handles[4],const uint32_t pitches[4],const uint32_t offsets[4],uint32_t *id,uint32_t flags)
{
    static int (*real)(int,uint32_t,uint32_t,uint32_t,const uint32_t*,const uint32_t*,const uint32_t*,uint32_t*,uint32_t);
    if (!real) real=dlsym(RTLD_NEXT,"drmModeAddFB2");
    int r=real(fd,w,h,format,handles,pitches,offsets,id,flags),e=errno;
    fprintf(stderr,"VF2_DRM addfb fd=%d size=%ux%u format=%08x handle=%u pitch=%u flags=%x ret=%d id=%u errno=%d\n",fd,w,h,format,handles[0],pitches[0],flags,r,r?0:*id,e);
    errno=e; return r;
}
int drmModeAddFB2WithModifiers(int fd,uint32_t w,uint32_t h,uint32_t format,const uint32_t handles[4],const uint32_t pitches[4],const uint32_t offsets[4],const uint64_t modifiers[4],uint32_t *id,uint32_t flags)
{
    static int (*real)(int,uint32_t,uint32_t,uint32_t,const uint32_t*,const uint32_t*,const uint32_t*,const uint64_t*,uint32_t*,uint32_t);
    if (!real) real=dlsym(RTLD_NEXT,"drmModeAddFB2WithModifiers");
    int r=real(fd,w,h,format,handles,pitches,offsets,modifiers,id,flags),e=errno;
    fprintf(stderr,"VF2_DRM addfb-mod fd=%d size=%ux%u format=%08x handle=%u pitch=%u modifier=%llx flags=%x ret=%d id=%u errno=%d\n",fd,w,h,format,handles[0],pitches[0],(unsigned long long)modifiers[0],flags,r,r?0:*id,e);
    errno=e; return r;
}

/* wl_drm authentication: Mesa (inside KWin) authenticates clients on its EGL fd for
 * card0, but VF2_DROP_RENDER_MASTER dropped master on that fd. DRM magic is per
 * device, so retry on another card0 fd in this process that does hold master
 * (KWin's KMS fd). */
#include <dirent.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
int drmAuthMagic(int fd, drm_magic_t magic)
{
    static int (*real_auth)(int, drm_magic_t);
    if (!real_auth)
        real_auth = dlsym(RTLD_NEXT, "drmAuthMagic");
    int r = real_auth(fd, magic);
    if (r == 0)
        return 0;
    struct stat want;
    if (fstat(fd, &want) != 0)
        return r;
    DIR *dir = opendir("/proc/self/fd");
    if (!dir)
        return r;
    struct dirent *e;
    while ((e = readdir(dir))) {
        int other = atoi(e->d_name);
        struct stat st;
        if (other <= 2 || other == fd || fstat(other, &st) != 0)
            continue;
        if (!S_ISCHR(st.st_mode) || st.st_rdev != want.st_rdev)
            continue;
        if (real_auth(other, magic) == 0) {
            fprintf(stderr, "VF2_DRM auth magic=%u via master fd=%d (requested fd=%d)\n", magic, other, fd);
            closedir(dir);
            return 0;
        }
    }
    closedir(dir);
    fprintf(stderr, "VF2_DRM auth magic=%u failed on all card fds\n", magic);
    return r;
}

/* Qt 6 on Debian is built for desktop OpenGL, so it asks EGL for EGL_OPENGL_BIT configs
 * and binds EGL_OPENGL_API. The vendor PowerVR EGL only provides OpenGL ES, so no
 * config matches, window surfaces fail (EGL_BAD_CONFIG) and Qt Quick apps such as
 * plasmashell render in software. With VF2_EGL_FORCE_GLES=1, ask for ES configs and
 * bind the ES API instead; Qt detects the ES context from its version string. */
#ifndef EGL_OPENGL_ES3_BIT_KHR
#define EGL_OPENGL_ES3_BIT_KHR 0x0040
#endif
EGLBoolean eglChooseConfig(EGLDisplay dpy, const EGLint *attribs, EGLConfig *configs,
                           EGLint size, EGLint *count)
{
    static EGLBoolean (*real_choose)(EGLDisplay, const EGLint *, EGLConfig *, EGLint, EGLint *);
    if (!real_choose)
        real_choose = dlsym(RTLD_NEXT, "eglChooseConfig");
    if (!attribs || !getenv("VF2_EGL_FORCE_GLES"))
        return real_choose(dpy, attribs, configs, size, count);
    EGLint fixed[128];
    int n = 0;
    for (; attribs[n] != EGL_NONE && n < 124; n += 2) {
        fixed[n] = attribs[n];
        fixed[n + 1] = attribs[n + 1];
        if (attribs[n] == EGL_RENDERABLE_TYPE && (attribs[n + 1] & EGL_OPENGL_BIT))
            fixed[n + 1] = (attribs[n + 1] & ~EGL_OPENGL_BIT) | EGL_OPENGL_ES2_BIT | EGL_OPENGL_ES3_BIT_KHR;
        if (attribs[n] == EGL_CONFORMANT && (attribs[n + 1] & EGL_OPENGL_BIT))
            fixed[n + 1] = (attribs[n + 1] & ~EGL_OPENGL_BIT) | EGL_OPENGL_ES2_BIT;
    }
    fixed[n] = EGL_NONE;
    return real_choose(dpy, fixed, configs, size, count);
}

EGLBoolean eglBindAPI(EGLenum api)
{
    static EGLBoolean (*real_bind)(EGLenum);
    if (!real_bind)
        real_bind = dlsym(RTLD_NEXT, "eglBindAPI");
    if (api == EGL_OPENGL_API && getenv("VF2_EGL_FORCE_GLES"))
        api = EGL_OPENGL_ES_API;
    return real_bind(api);
}
