#ifndef LAUNCHER_COMPAT_H
#define LAUNCHER_COMPAT_H

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* ========= Platform detection ========= */

#if defined(_WIN32) || defined(_WIN64)
  #define PLATFORM_WINDOWS 1
#else
  #define PLATFORM_WINDOWS 0
#endif

#if defined(_MSC_VER)
  #define COMPILER_MSVC 1
#else
  #define COMPILER_MSVC 0
#endif

#ifdef _WIN32
#include <string.h>  // Windows version
#else
#include <strings.h>  // Linux/Unix version
#endif

#ifdef _WIN32
#define strdup _strdup  // Define strdup for Windows if needed
#endif

#ifdef _WIN32
#define strtok_r strtok_s  // Use strtok_s for Windows (instead of strtok_r)
#endif

// Your code continues below...

/* ========= strdup replacement (owned) ========= */

static inline char* compat_strdup(const char* s) {
    if (!s) return NULL;
    size_t len = strlen(s) + 1;
    char* p = (char*)malloc(len);
    if (p) memcpy(p, s, len);
    return p;
}

#define _strdup compat_strdup

/* ========= case-insensitive compare ========= */

#if COMPILER_MSVC
  #define _stricmp _stricmp
#else
  static inline int compat_stricmp(const char* a, const char* b) {
      while (*a && *b) {
          char ca = (*a >= 'A' && *a <= 'Z') ? *a + 32 : *a;
          char cb = (*b >= 'A' && *b <= 'Z') ? *b + 32 : *b;
          if (ca != cb) return (unsigned char)ca - (unsigned char)cb;
          a++; b++;
      }
      return (unsigned char)*a - (unsigned char)*b;
  }
  #define _stricmp compat_stricmp
#endif

/* ========= strtok_s replacement (deterministic) ========= */
/* Simple MSVC-compatible behavior */

static inline char* compat_strtok_s(
    char* str,
    const char* delim,
    char** context
) {
    char* start = str ? str : *context;
    if (!start) return NULL;

    start += strspn(start, delim);
    if (*start == '\0') {
        *context = NULL;
        return NULL;
    }

    char* end = start + strcspn(start, delim);
    if (*end) {
        *end = '\0';
        *context = end + 1;
    } else {
        *context = NULL;
    }

    return start;
}

#define strtok_s compat_strtok_s

/* ========= Sleep (milliseconds) ========= */

#if PLATFORM_WINDOWS
  #include <windows.h>
  static inline void SleepMs(unsigned long ms) {
      Sleep(ms);
  }
#else
  #include <time.h>
  static inline void SleepMs(unsigned long ms) {
      struct timespec ts;
      ts.tv_sec  = ms / 1000;
      ts.tv_nsec = (ms % 1000) * 1000000UL;
      nanosleep(&ts, NULL);
  }
#endif

/* ========= ShellExecute threshold ========= */

#define SHELL_EXEC_ERROR_THRESHOLD ((intptr_t)32)

#endif /* LAUNCHER_COMPAT_H */
