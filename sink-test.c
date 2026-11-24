#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc != 2 || (strcmp(argv[1], "get") != 0 &&
                      strcmp(argv[1], "internal") != 0 &&
                      strcmp(argv[1], "usb") != 0)) {
        fprintf(stderr, "Usage: %s get|internal|usb\n", argv[0]);
        return 2;
    }

    void *lib = dlopen("libmsettings.so", RTLD_NOW);
    if (!lib) {
        fprintf(stderr, "Cannot load NextUI settings: %s\n", dlerror());
        return 1;
    }
    void (*init)(void) = dlsym(lib, "InitSettings");
    void (*quit)(void) = dlsym(lib, "QuitSettings");
    int (*get)(void) = dlsym(lib, "GetAudioSink");
    void (*set)(int) = dlsym(lib, "SetAudioSink");
    if (!init || !quit || !get || !set) {
        fprintf(stderr, "NextUI settings API is incomplete: %s\n", dlerror());
        dlclose(lib);
        return 1;
    }
    if (!getenv("USERDATA_PATH") || !getenv("DEVICE")) {
        fprintf(stderr, "Missing NextUI environment\n");
        dlclose(lib);
        return 1;
    }
    init();
    int before = get();
    if (strcmp(argv[1], "get") != 0)
        set(strcmp(argv[1], "internal") == 0 ? 0 : 2);
    printf("Audio sink: %d -> %d\n", before, get());
    quit();
    dlclose(lib);
    return 0;
}
