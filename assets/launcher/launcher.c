/**
 * launcher.c - Game Launcher
 *
 * A complete C port of the Python game launcher script.
 *
 * Compilation (using MinGW-w64):
 * gcc -o launcher.exe launcher.c inih/ini.c -luser32 -lshlwapi -lole32 -lpsapi -Wall
 *
 * Dependencies:
 * - inih library (https://github.com/benhoyt/inih) for INI parsing.
 *   Place ini.h and ini.c in an 'inih' subdirectory.
 */

#define _WIN32_WINNT 0x0600 // Required for some modern Windows API functions
#include "compat.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tlhelp32.h> // For process snapshots
#include <shlwapi.h>   // For PathRemoveFileSpecA, PathAppendA
#include <psapi.h>     // For GetModuleBaseName
#include <time.h>

// Include the inih library header
#include "inih/ini.h"
#include <stdint.h>   // for intptr_t

#ifndef _MSC_VER
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

// Include common definitions and tray menu
#include "launcher_common.h"
#include "tray_menu.h"

// --- Tracked Process Structure ---
typedef struct TrackedProcess {
    char name[MAX_NAME_LEN];
    PROCESS_INFORMATION pi;
    struct TrackedProcess* next;
} TrackedProcess;

// --- Global State Variables ---
GameConfiguration G_CONFIG;
PROCESS_INFORMATION G_GAME_PROCESS_INFO;
TrackedProcess* G_TRACKED_PROCESSES = NULL;
HANDLE G_BORDERLESS_PROCESS = NULL;
HWND G_TASKBAR_HWND = NULL;
BOOL G_TASKBAR_WAS_HIDDEN = FALSE;
char G_LOG_PATH[MAX_PATH_LEN] = "";
char G_HOME_DIR[MAX_PATH_LEN] = "";
char G_GAME_EXE_NAME[MAX_NAME_LEN] = "";
char G_PID_FILE[MAX_PATH_LEN] = "";
BOOL G_IS_ADMIN = FALSE;
int G_VERBOSE_LEVEL = 2; // Default to debug-level logging
int G_CLI_VERBOSE_SET = 0;

// --- Function Prototypes ---
void show_message(const char* message);
void log_message(const char* level, const char* message);
void log_debug(const char* message);
static int config_handler(void* user, const char* section, const char* name, const char* value);
int load_configuration(const char* ini_path);
void resolve_config_paths();
void execute_sequence(const char* sequence_str, int is_exit_sequence);
void execute_action(const char* action, int is_exit_sequence);
void run_game_process();
BOOL run_process(const char* command, const char* working_dir, BOOL wait, PROCESS_INFORMATION* pi);
void terminate_process_tree(DWORD pid);
void kill_process_by_name(const char* process_name);
void set_taskbar_visibility(BOOL show);
char* resolve_path(const char* path, char* resolved, size_t resolved_size);
void trim_whitespace(char* str);
void add_tracked_process(const char* name, PROCESS_INFORMATION* pi);
void remove_tracked_process(const char* name);
void kill_all_tracked_processes();
void ensure_cleanup();
BOOL check_admin();
BOOL check_instances();
void write_pid_file();
void cleanup_pid_file();
void string_replace(char* dest, size_t dest_size, const char* src, const char* find, const char* replace);

// Action function prototypes
void action_run_controller_mapper(int is_exit);
void action_kill_controller_mapper();
void action_run_monitor_config_game();
void action_run_monitor_config_desktop();
void action_hide_taskbar();
void action_show_taskbar();
void action_run_borderless();
void action_kill_borderless();
void action_run_cloud_sync();
void action_run_generic_app(const char* app_path, int wait, const char* options, const char* args);
void action_kill_game();
void action_kill_process_list();
void action_mount_iso();
void action_unmount_iso();
void action_mount_disc_with_app();
void action_unmount_disc_with_app();
void action_run_audio_game();
void action_run_audio_desktop();

// --- Logging Implementation ---
void log_message(const char* level, const char* message) {
    if (G_LOG_PATH[0] == '\0') return;
    
    FILE* log_file = fopen(G_LOG_PATH, "a");
    if (!log_file) return;
    
    time_t now = time(NULL);
    struct tm* timeinfo = localtime(&now);
    char time_str[64];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", timeinfo);
    
    fprintf(log_file, "%s - %s - %s\n", time_str, level, message);
    fclose(log_file);
    
    // If verbose mode, also print to console
    if (G_VERBOSE_LEVEL > 0) {
        if (G_VERBOSE_LEVEL >= 2) {
            // Very verbose: include timestamp and level
            printf("%s - %s - %s\n", time_str, level, message);
        } else {
            // Verbose: just level and message
            printf("%s - %s\n", level, message);
        }
    }
}

void show_message(const char* message) {
    if (G_VERBOSE_LEVEL > 0) {
        printf("[Launcher] %s\n", message);
    }
    log_message("INFO", message);
}

void log_debug(const char* message) {
    if (G_VERBOSE_LEVEL >= 1) {
        log_message("DEBUG", message);
    }
}

// --- String Utilities ---
void trim_whitespace(char* str) {
    if (!str) return;
    
    // Trim leading whitespace
    char* start = str;
    while (*start && (*start == ' ' || *start == '\t' || *start == '\n' || *start == '\r')) {
        start++;
    }
    
    if (start != str) {
        memmove(str, start, strlen(start) + 1);
    }
    
    // Trim trailing whitespace
    size_t len = strlen(str);
    while (len > 0 && (str[len-1] == ' ' || str[len-1] == '\t' || str[len-1] == '\n' || str[len-1] == '\r')) {
        str[len-1] = '\0';
        len--;
    }
}

// --- String Replacement Helper ---
void string_replace(char* dest, size_t dest_size, const char* src, const char* find, const char* replace) {
    if (!src || !find || !replace || !dest || dest_size == 0) return;
    
    char temp[MAX_CMD_LEN * 2];
    const char* pos = src;
    char* out = temp;
    size_t find_len = strlen(find);
    size_t replace_len = strlen(replace);
    size_t remaining = sizeof(temp) - 1;
    
    while (*pos && remaining > 0) {
        if (strncmp(pos, find, find_len) == 0) {
            // Found match, replace it
            size_t copy_len = (replace_len < remaining) ? replace_len : remaining;
            strncpy(out, replace, copy_len);
            out += copy_len;
            remaining -= copy_len;
            pos += find_len;
        } else {
            *out++ = *pos++;
            remaining--;
        }
    }
    *out = '\0';
    
    strncpy(dest, temp, dest_size - 1);
    dest[dest_size - 1] = '\0';
}

// --- Path Resolution ---
char* resolve_path(const char* path, char* resolved, size_t resolved_size) {
    if (!path || !resolved || resolved_size == 0) return NULL;
    
    char temp[MAX_CMD_LEN * 2];
    strncpy(temp, path, sizeof(temp) - 1);
    temp[sizeof(temp) - 1] = '\0';
    
    // Variable substitution: $GAMENAME, $HOME, $ISO
    string_replace(temp, sizeof(temp), temp, "$GAMENAME", G_CONFIG.name);
    string_replace(temp, sizeof(temp), temp, "$HOME", G_HOME_DIR);
    string_replace(temp, sizeof(temp), temp, "$ISO", G_CONFIG.iso_path);
    
    // Resolve relative paths against the profile directory (G_HOME_DIR)
    if (strchr(temp, ':') == NULL && temp[0] != '\\' && temp[0] != '/' && strlen(temp) > 0) {
        char abs_path[MAX_CMD_LEN * 2];
        snprintf(abs_path, sizeof(abs_path), "%s\\%s", G_HOME_DIR, temp);
        strncpy(temp, abs_path, sizeof(temp) - 1);
        temp[sizeof(temp) - 1] = '\0';
    }
    
    strncpy(resolved, temp, resolved_size - 1);
    resolved[resolved_size - 1] = '\0';
    
    return resolved;
}

// --- Tracked Process Management ---
void add_tracked_process(const char* name, PROCESS_INFORMATION* pi) {
    TrackedProcess* tp = (TrackedProcess*)malloc(sizeof(TrackedProcess));
    if (!tp) return;
    
    strncpy(tp->name, name, MAX_NAME_LEN - 1);
    tp->name[MAX_NAME_LEN - 1] = '\0';
    tp->pi = *pi;
    tp->next = G_TRACKED_PROCESSES;
    G_TRACKED_PROCESSES = tp;
}

void remove_tracked_process(const char* name) {
    TrackedProcess** current = &G_TRACKED_PROCESSES;
    while (*current) {
        if (strcmp((*current)->name, name) == 0) {
            TrackedProcess* to_remove = *current;
            *current = (*current)->next;
            free(to_remove);
            return;
        }
        current = &(*current)->next;
    }
}

TrackedProcess* find_tracked_process(const char* name) {
    TrackedProcess* current = G_TRACKED_PROCESSES;
    while (current) {
        if (strcmp(current->name, name) == 0) {
            return current;
        }
        current = current->next;
    }
    return NULL;
}

void kill_all_tracked_processes() {
    show_message("Cleaning up background processes...");
    
    TrackedProcess* current = G_TRACKED_PROCESSES;
    while (current) {
        terminate_process_tree(current->pi.dwProcessId);
        CloseHandle(current->pi.hProcess);
        CloseHandle(current->pi.hThread);
        current = current->next;
    }
    
    // Free all tracked processes
    while (G_TRACKED_PROCESSES) {
        TrackedProcess* to_remove = G_TRACKED_PROCESSES;
        G_TRACKED_PROCESSES = G_TRACKED_PROCESSES->next;
        free(to_remove);
    }
}

// --- INI Parsing Handler ---
static int config_handler(void* user, const char* section, const char* name, const char* value) {
    GameConfiguration* pConfig = (GameConfiguration*)user;
    
    #define MATCH(s, n) (_stricmp(section, s) == 0 && _stricmp(name, n) == 0)
    #define SET_STR(field) strncpy(pConfig->field, value, sizeof(pConfig->field) - 1)
    #define SET_BOOL(field) pConfig->field = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0 || strcmp(value, "True") == 0)
    #define SET_INT(field) pConfig->field = atoi(value)

    // [Game] section
    if (MATCH("Game", "Executable")) {
        SET_STR(executable);
    } else if (MATCH("Game", "Directory")) {
        SET_STR(directory);
    } else if (MATCH("Game", "Name")) {
        SET_STR(name);
    } else if (MATCH("Game", "IsoPath")) {
        SET_STR(iso_path);
    } else if (MATCH("Game", "logging_verbosity")) {
        SET_STR(logging_verbosity);
    }
    // [Paths] section
    else if (MATCH("Paths", "ControllerMapperApp")) {
        SET_STR(controller_mapper_app);
    } else if (MATCH("Paths", "ControllerMapperOptions")) {
        SET_STR(controller_mapper_options);
    } else if (MATCH("Paths", "ControllerMapperArguments")) {
        SET_STR(controller_mapper_arguments);
    } else if (MATCH("Paths", "BorderlessWindowingApp")) {
        SET_STR(borderless_windowing_app);
    } else if (MATCH("Paths", "BorderlessWindowingOptions")) {
        SET_STR(borderless_options);
    } else if (MATCH("Paths", "BorderlessWindowingArguments")) {
        SET_STR(borderless_arguments);
    } else if (MATCH("Paths", "MonitorApp")) {
        SET_STR(monitorapp);
    } else if (MATCH("Paths", "MonitorAppOptions")) {
        SET_STR(monitorapp_options);
    } else if (MATCH("Paths", "MonitorAppArguments")) {
        SET_STR(monitorapp_arguments);
    } else if (MATCH("Paths", "Player1Profile")) {
        SET_STR(player1_profile);
    } else if (MATCH("Paths", "Player2Profile")) {
        SET_STR(player2_profile);
    } else if (MATCH("Paths", "DeskProfile")) {
        SET_STR(desk_profile);
    } else if (MATCH("Paths", "MonitorGameConfig")) {
        SET_STR(monitor_game_config);
    } else if (MATCH("Paths", "MonitorDesktopConfig")) {
        SET_STR(monitor_desk_config);
    } else if (MATCH("Paths", "CloudApp")) {
        SET_STR(cloud_app);
    } else if (MATCH("Paths", "CloudAppOptions")) {
        SET_STR(cloud_app_options);
    } else if (MATCH("Paths", "CloudAppArguments")) {
        SET_STR(cloud_app_arguments);
    } else if (MATCH("Paths", "DiscMountApp")) {
        SET_STR(disc_mount_app);
    } else if (MATCH("Paths", "DiscMountOptions")) {
        SET_STR(disc_mount_options);
    } else if (MATCH("Paths", "DiscMountArguments")) {
        SET_STR(disc_mount_arguments);
    } else if (MATCH("Paths", "DiscMountWait")) {
        SET_BOOL(disc_mount_wait);
    } else if (MATCH("Paths", "DiscUnmountApp")) {
        SET_STR(disc_unmount_app);
    } else if (MATCH("Paths", "DiscUnmountOptions")) {
        SET_STR(disc_unmount_options);
    } else if (MATCH("Paths", "DiscUnmountArguments")) {
        SET_STR(disc_unmount_arguments);
    } else if (MATCH("Paths", "DiscUnmountWait")) {
        SET_BOOL(disc_unmount_wait);
    }
    // [ControllerMapper] section
    else if (MATCH("ControllerMapper", "enablecontrollermapper")) {
        SET_BOOL(controller_mapper_enabled);
    } else if (MATCH("ControllerMapper", "controllermapperpath")) {
        SET_STR(controller_mapper_app);
    } else if (MATCH("ControllerMapper", "controllermapperpathoptions")) {
        SET_STR(controller_mapper_options);
    } else if (MATCH("ControllerMapper", "controllermapperpatharguments")) {
        SET_STR(controller_mapper_arguments);
    }
    // [BorderlessWindowing] section
    else if (MATCH("BorderlessWindowing", "enableborderlesswindowing")) {
        SET_BOOL(borderless_windowing_enabled);
    } else if (MATCH("BorderlessWindowing", "borderlesswindowingpath")) {
        SET_STR(borderless_windowing_app);
    } else if (MATCH("BorderlessWindowing", "borderlesswindowingpathoptions")) {
        SET_STR(borderless_options);
    } else if (MATCH("BorderlessWindowing", "borderlesswindowingpatharguments")) {
        SET_STR(borderless_arguments);
    }
    // [Monitor] section
    else if (MATCH("Monitor", "enablemonitorapp")) {
        SET_BOOL(monitorapp_enabled);
    } else if (MATCH("Monitor", "monitorapppath")) {
        SET_STR(monitorapp);
    } else if (MATCH("Monitor", "monitorapppathoptions")) {
        SET_STR(monitorapp_options);
    } else if (MATCH("Monitor", "monitorapppatharguments")) {
        SET_STR(monitorapp_arguments);
    }
    // [DiscMount] section
    else if (MATCH("DiscMount", "enablediscmount")) {
        SET_BOOL(disc_mount_enabled);
    } else if (MATCH("DiscMount", "discmountpath")) {
        SET_STR(disc_mount_app);
    } else if (MATCH("DiscMount", "discmountpathoptions")) {
        SET_STR(disc_mount_options);
    } else if (MATCH("DiscMount", "discmountpatharguments")) {
        SET_STR(disc_mount_arguments);
    } else if (MATCH("DiscMount", "discmountpathrunwait")) {
        SET_BOOL(disc_mount_wait);
    }
    // [AudioApp] section
    else if (MATCH("AudioApp", "enableaudioapp")) {
        SET_BOOL(audio_app_enabled);
    } else if (MATCH("AudioApp", "audioapppath")) {
        SET_STR(audio_app_path);
    } else if (MATCH("AudioApp", "audioapppathoptions")) {
        SET_STR(audio_app_options);
    } else if (MATCH("AudioApp", "audioapppatharguments")) {
        SET_STR(audio_app_arguments);
    } else if (MATCH("AudioApp", "audioapppathrunwait")) {
        SET_BOOL(audio_app_run_wait);
    }
    // [DiscDrivePrefs] section
    else if (MATCH("DiscDrivePrefs", "enablediscmountcfg")) {
        SET_BOOL(disc_mount_cfg_enabled);
    } else if (MATCH("DiscDrivePrefs", "discmountcfgpath")) {
        SET_STR(disc_mount_cfg);
    } else if (MATCH("DiscDrivePrefs", "discmountcfgpathoptions")) {
        SET_STR(disc_mount_cfg_options);
    } else if (MATCH("DiscDrivePrefs", "discmountcfgpatharguments")) {
        SET_STR(disc_mount_cfg_arguments);
    } else if (MATCH("DiscDrivePrefs", "enablediscunmountcfg")) {
        SET_BOOL(disc_unmount_cfg_enabled);
    } else if (MATCH("DiscDrivePrefs", "discunmountcfgpath")) {
        SET_STR(disc_unmount_cfg);
    } else if (MATCH("DiscDrivePrefs", "discunmountcfgpathoptions")) {
        SET_STR(disc_unmount_cfg_options);
    } else if (MATCH("DiscDrivePrefs", "discunmountcfgpatharguments")) {
        SET_STR(disc_unmount_cfg_arguments);
    }
    // [mapperprofiles] section
    else if (MATCH("mapperprofiles", "enableplayer1profile")) {
        SET_BOOL(player1_profile_enabled);
    } else if (MATCH("mapperprofiles", "enableplayer2profile")) {
        SET_BOOL(player2_profile_enabled);
    } else if (MATCH("mapperprofiles", "enabledeskprofile")) {
        SET_BOOL(desk_profile_enabled);
    } else if (MATCH("mapperprofiles", "player1profile")) {
        SET_STR(player1_profile);
    } else if (MATCH("mapperprofiles", "player2profile")) {
        SET_STR(player2_profile);
    } else if (MATCH("mapperprofiles", "deskprofile")) {
        SET_STR(desk_profile);
    } else if (MATCH("mapperprofiles", "player1profileoptions")) {
        SET_STR(player1_profile_options);
    } else if (MATCH("mapperprofiles", "player1profilearguments")) {
        SET_STR(player1_profile_arguments);
    } else if (MATCH("mapperprofiles", "player2profileoptions")) {
        SET_STR(player2_profile_options);
    } else if (MATCH("mapperprofiles", "player2profilearguments")) {
        SET_STR(player2_profile_arguments);
    } else if (MATCH("mapperprofiles", "deskprofileoptions")) {
        SET_STR(desk_profile_options);
    } else if (MATCH("mapperprofiles", "deskprofilearguments")) {
        SET_STR(desk_profile_arguments);
    }
    // [MonitorLayouts] section
    else if (MATCH("MonitorLayouts", "enablemonitorgamecfg")) {
        SET_BOOL(monitor_game_cfg_enabled);
    } else if (MATCH("MonitorLayouts", "enablemonitordeskcfg")) {
        SET_BOOL(monitor_desk_cfg_enabled);
    } else if (MATCH("MonitorLayouts", "monitorgamecfg")) {
        SET_STR(monitor_game_config);
    } else if (MATCH("MonitorLayouts", "monitordeskcfg")) {
        SET_STR(monitor_desk_config);
    } else if (MATCH("MonitorLayouts", "monitorgamecfgoptions")) {
        SET_STR(monitor_game_config_options);
    } else if (MATCH("MonitorLayouts", "monitorgamecfgarguments")) {
        SET_STR(monitor_game_config_arguments);
    } else if (MATCH("MonitorLayouts", "monitordeskcfgoptions")) {
        SET_STR(monitor_desk_config_options);
    } else if (MATCH("MonitorLayouts", "monitordeskcfgarguments")) {
        SET_STR(monitor_desk_config_arguments);
    }
    // [BorderlessProfiles] section
    else if (MATCH("BorderlessProfiles", "enableunbordercfg")) {
        SET_BOOL(unborder_cfg_enabled);
    } else if (MATCH("BorderlessProfiles", "unbordercfgpath")) {
        SET_STR(unborder_cfg);
    } else if (MATCH("BorderlessProfiles", "unbordercfgpathoptions")) {
        SET_STR(unborder_cfg_options);
    } else if (MATCH("BorderlessProfiles", "unbordercfgpatharguments")) {
        SET_STR(unborder_cfg_arguments);
    } else if (MATCH("BorderlessProfiles", "enablerebordercfg")) {
        SET_BOOL(reborder_cfg_enabled);
    } else if (MATCH("BorderlessProfiles", "rebordercfgpath")) {
        SET_STR(reborder_cfg);
    } else if (MATCH("BorderlessProfiles", "rebordercfgpathoptions")) {
        SET_STR(reborder_cfg_options);
    } else if (MATCH("BorderlessProfiles", "rebordercfgpatharguments")) {
        SET_STR(reborder_cfg_arguments);
    }
    // [AudioPresets] section
    else if (MATCH("AudioPresets", "enableaudiogamecfg")) {
        SET_BOOL(audio_game_cfg_enabled);
    } else if (MATCH("AudioPresets", "audiogamecfgpath")) {
        SET_STR(audio_game_cfg);
    } else if (MATCH("AudioPresets", "audiogamecfgpathoptions")) {
        SET_STR(audio_game_cfg_options);
    } else if (MATCH("AudioPresets", "audiogamecfgpatharguments")) {
        SET_STR(audio_game_cfg_arguments);
    } else if (MATCH("AudioPresets", "enableaudiodeskcfg")) {
        SET_BOOL(audio_desk_cfg_enabled);
    } else if (MATCH("AudioPresets", "audiodeskcfgpath")) {
        SET_STR(audio_desk_cfg);
    } else if (MATCH("AudioPresets", "audiodeskcfgpathoptions")) {
        SET_STR(audio_desk_cfg_options);
    } else if (MATCH("AudioPresets", "audiodeskcfgpatharguments")) {
        SET_STR(audio_desk_cfg_arguments);
    }
    // Backward compatibility: old DiscMountCfg/DiscUnmountCfg sections
    else if (MATCH("DiscMountCfg", "enablediscmountcfg")) {
        SET_BOOL(disc_mount_cfg_enabled);
    } else if (MATCH("DiscMountCfg", "discmountcfgpath")) {
        SET_STR(disc_mount_cfg);
    } else if (MATCH("DiscMountCfg", "discmountcfgpathoptions")) {
        SET_STR(disc_mount_cfg_options);
    } else if (MATCH("DiscMountCfg", "discmountcfgpatharguments")) {
        SET_STR(disc_mount_cfg_arguments);
    } else if (MATCH("DiscUnmountCfg", "enablediscunmountcfg")) {
        SET_BOOL(disc_unmount_cfg_enabled);
    } else if (MATCH("DiscUnmountCfg", "discunmountcfgpath")) {
        SET_STR(disc_unmount_cfg);
    } else if (MATCH("DiscUnmountCfg", "discunmountcfgpathoptions")) {
        SET_STR(disc_unmount_cfg_options);
    } else if (MATCH("DiscUnmountCfg", "discunmountcfgpatharguments")) {
        SET_STR(disc_unmount_cfg_arguments);
    // Backward compatibility: old AudioGameCfg/AudioDeskCfg sections
    } else if (MATCH("AudioDeskCfg", "enableaudiodeskcfg")) {
        SET_BOOL(audio_desk_cfg_enabled);
    } else if (MATCH("AudioDeskCfg", "audiodeskcfgpath")) {
        SET_STR(audio_desk_cfg);
    } else if (MATCH("AudioDeskCfg", "audiodeskcfgpathoptions")) {
        SET_STR(audio_desk_cfg_options);
    } else if (MATCH("AudioDeskCfg", "audiodeskcfgpatharguments")) {
        SET_STR(audio_desk_cfg_arguments);
    }
    // [Launcher] section (for compatibility with Python-created Game.ini)
    else if (MATCH("Launcher", "runasadmin")) {
        SET_BOOL(run_as_admin);
    } else if (MATCH("Launcher", "hidetaskbar")) {
        SET_BOOL(hide_taskbar);
    } else if (MATCH("Launcher", "borderless")) {
        strncpy(pConfig->borderless, value, sizeof(pConfig->borderless) - 1);
    } else if (MATCH("Launcher", "usekilllist")) {
        SET_BOOL(use_kill_list);
    } else if (MATCH("Launcher", "killlist")) {
        SET_STR(kill_list);
    } else if (MATCH("Launcher", "terminateborderlessonexit")) {
        SET_BOOL(terminate_borderless_on_exit);
    }
    // [Options] section
    else if (MATCH("Options", "RunAsAdmin")) {
        SET_BOOL(run_as_admin);
    } else if (MATCH("Options", "HideTaskbar")) {
        SET_BOOL(hide_taskbar);
    } else if (MATCH("Options", "Borderless")) {
        strncpy(pConfig->borderless, value, sizeof(pConfig->borderless) - 1);
    } else if (MATCH("Options", "UseKillList")) {
        SET_BOOL(use_kill_list);
    } else if (MATCH("Options", "TerminateBorderlessOnExit")) {
        SET_BOOL(terminate_borderless_on_exit);
    } else if (MATCH("Options", "KillList")) {
        SET_STR(kill_list);
    } else if (MATCH("Options", "BackupSaves")) {
        SET_BOOL(backup_saves);
    } else if (MATCH("Options", "MaxBackups")) {
        SET_INT(max_backups);
    }
    // [PreLaunch] section
    else if (MATCH("PreLaunch", "App1")) {
        SET_STR(pre_launch_app_1);
    } else if (MATCH("PreLaunch", "App1Options")) {
        SET_STR(pre_launch_app_1_options);
    } else if (MATCH("PreLaunch", "App1Arguments")) {
        SET_STR(pre_launch_app_1_arguments);
    } else if (MATCH("PreLaunch", "App1Wait")) {
        SET_BOOL(pre_launch_app_1_wait);
    } else if (MATCH("PreLaunch", "App2")) {
        SET_STR(pre_launch_app_2);
    } else if (MATCH("PreLaunch", "App2Options")) {
        SET_STR(pre_launch_app_2_options);
    } else if (MATCH("PreLaunch", "App2Arguments")) {
        SET_STR(pre_launch_app_2_arguments);
    } else if (MATCH("PreLaunch", "App2Wait")) {
        SET_BOOL(pre_launch_app_2_wait);
    } else if (MATCH("PreLaunch", "App3")) {
        SET_STR(pre_launch_app_3);
    } else if (MATCH("PreLaunch", "App3Options")) {
        SET_STR(pre_launch_app_3_options);
    } else if (MATCH("PreLaunch", "App3Arguments")) {
        SET_STR(pre_launch_app_3_arguments);
    } else if (MATCH("PreLaunch", "App3Wait")) {
        SET_BOOL(pre_launch_app_3_wait);
    }
    // [Pre1], [Pre2], [Pre3] sections (for compatibility with Python-created Game.ini)
    else if (MATCH("Pre1", "pre1path")) {
        SET_STR(pre_launch_app_1);
    } else if (MATCH("Pre1", "pre1pathoptions")) {
        SET_STR(pre_launch_app_1_options);
    } else if (MATCH("Pre1", "pre1patharguments")) {
        SET_STR(pre_launch_app_1_arguments);
    } else if (MATCH("Pre1", "pre1pathrunwait")) {
        SET_BOOL(pre_launch_app_1_wait);
    } else if (MATCH("Pre2", "pre2path")) {
        SET_STR(pre_launch_app_2);
    } else if (MATCH("Pre2", "pre2pathoptions")) {
        SET_STR(pre_launch_app_2_options);
    } else if (MATCH("Pre2", "pre2patharguments")) {
        SET_STR(pre_launch_app_2_arguments);
    } else if (MATCH("Pre2", "pre2pathrunwait")) {
        SET_BOOL(pre_launch_app_2_wait);
    } else if (MATCH("Pre3", "pre3path")) {
        SET_STR(pre_launch_app_3);
    } else if (MATCH("Pre3", "pre3pathoptions")) {
        SET_STR(pre_launch_app_3_options);
    } else if (MATCH("Pre3", "pre3patharguments")) {
        SET_STR(pre_launch_app_3_arguments);
    } else if (MATCH("Pre3", "pre3pathrunwait")) {
        SET_BOOL(pre_launch_app_3_wait);
    }
    // [PostLaunch] section
    else if (MATCH("PostLaunch", "App1")) {
        SET_STR(post_launch_app_1);
    } else if (MATCH("PostLaunch", "App1Options")) {
        SET_STR(post_launch_app_1_options);
    } else if (MATCH("PostLaunch", "App1Arguments")) {
        SET_STR(post_launch_app_1_arguments);
    } else if (MATCH("PostLaunch", "App1Wait")) {
        SET_BOOL(post_launch_app_1_wait);
    } else if (MATCH("PostLaunch", "App2")) {
        SET_STR(post_launch_app_2);
    } else if (MATCH("PostLaunch", "App2Options")) {
        SET_STR(post_launch_app_2_options);
    } else if (MATCH("PostLaunch", "App2Arguments")) {
        SET_STR(post_launch_app_2_arguments);
    } else if (MATCH("PostLaunch", "App2Wait")) {
        SET_BOOL(post_launch_app_2_wait);
    } else if (MATCH("PostLaunch", "App3")) {
        SET_STR(post_launch_app_3);
    } else if (MATCH("PostLaunch", "App3Options")) {
        SET_STR(post_launch_app_3_options);
    } else if (MATCH("PostLaunch", "App3Arguments")) {
        SET_STR(post_launch_app_3_arguments);
    } else if (MATCH("PostLaunch", "App3Wait")) {
        SET_BOOL(post_launch_app_3_wait);
    } else if (MATCH("PostLaunch", "JustAfterLaunchApp")) {
        SET_STR(just_after_launch_app);
    } else if (MATCH("PostLaunch", "JustAfterLaunchOptions")) {
        SET_STR(just_after_launch_options);
    } else if (MATCH("PostLaunch", "JustAfterLaunchArguments")) {
        SET_STR(just_after_launch_arguments);
    } else if (MATCH("PostLaunch", "JustAfterLaunchWait")) {
        SET_BOOL(just_after_launch_wait);
    } else if (MATCH("PostLaunch", "JustBeforeExitApp")) {
        SET_STR(just_before_exit_app);
    } else if (MATCH("PostLaunch", "JustBeforeExitOptions")) {
        SET_STR(just_before_exit_options);
    } else if (MATCH("PostLaunch", "JustBeforeExitArguments")) {
        SET_STR(just_before_exit_arguments);
    } else if (MATCH("PostLaunch", "JustBeforeExitWait")) {
        SET_BOOL(just_before_exit_wait);
    }
    // [Post1], [Post2], [Post3], [JustAfterLaunch], [JustBeforeExit] sections (for compatibility with Python-created Game.ini)
    else if (MATCH("Post1", "post1path")) {
        SET_STR(post_launch_app_1);
    } else if (MATCH("Post1", "post1pathoptions")) {
        SET_STR(post_launch_app_1_options);
    } else if (MATCH("Post1", "post1patharguments")) {
        SET_STR(post_launch_app_1_arguments);
    } else if (MATCH("Post1", "post1pathrunwait")) {
        SET_BOOL(post_launch_app_1_wait);
    } else if (MATCH("Post2", "post2path")) {
        SET_STR(post_launch_app_2);
    } else if (MATCH("Post2", "post2pathoptions")) {
        SET_STR(post_launch_app_2_options);
    } else if (MATCH("Post2", "post2patharguments")) {
        SET_STR(post_launch_app_2_arguments);
    } else if (MATCH("Post2", "post2pathrunwait")) {
        SET_BOOL(post_launch_app_2_wait);
    } else if (MATCH("Post3", "post3path")) {
        SET_STR(post_launch_app_3);
    } else if (MATCH("Post3", "post3pathoptions")) {
        SET_STR(post_launch_app_3_options);
    } else if (MATCH("Post3", "post3patharguments")) {
        SET_STR(post_launch_app_3_arguments);
    } else if (MATCH("Post3", "post3pathrunwait")) {
        SET_BOOL(post_launch_app_3_wait);
    } else if (MATCH("JustAfterLaunch", "path")) {
        SET_STR(just_after_launch_app);
    } else if (MATCH("JustAfterLaunch", "pathoptions")) {
        SET_STR(just_after_launch_options);
    } else if (MATCH("JustAfterLaunch", "patharguments")) {
        SET_STR(just_after_launch_arguments);
    } else if (MATCH("JustAfterLaunch", "pathrunwait")) {
        SET_BOOL(just_after_launch_wait);
    } else if (MATCH("JustBeforeExit", "path")) {
        SET_STR(just_before_exit_app);
    } else if (MATCH("JustBeforeExit", "pathoptions")) {
        SET_STR(just_before_exit_options);
    } else if (MATCH("JustBeforeExit", "patharguments")) {
        SET_STR(just_before_exit_arguments);
    } else if (MATCH("JustBeforeExit", "pathrunwait")) {
        SET_BOOL(just_before_exit_wait);
    }
    // [Sequences] section
    else if (MATCH("Sequences", "LaunchSequence")) {
        SET_STR(launch_sequence);
    } else if (MATCH("Sequences", "ExitSequence")) {
        SET_STR(exit_sequence);
    }
    else {
        return 0; // unknown section/name
    }
    return 1;
    
    #undef MATCH
    #undef SET_STR
    #undef SET_BOOL
    #undef SET_INT
}

int load_configuration(const char* ini_path) {
    // Set up log path
    char log_path[MAX_PATH_LEN];
    strncpy(log_path, ini_path, MAX_PATH_LEN - 1);
    log_path[MAX_PATH_LEN - 1] = '\0';
    char* last_slash = strrchr(log_path, '\\');
    if (!last_slash) last_slash = strrchr(log_path, '/');
    if (last_slash) {
        *(last_slash + 1) = '\0';
        strncat(log_path, "launcher.log", MAX_PATH_LEN - strlen(log_path) - 1);
        strncpy(G_LOG_PATH, log_path, MAX_PATH_LEN - 1);
    }
    
    log_debug("Loading configuration from Game.ini");
    
    if (ini_parse(ini_path, config_handler, &G_CONFIG) < 0) {
        show_message("Can't load 'Game.ini'");
        return 1;
    }
    show_message("Configuration loaded successfully.");
    
    // Resolve all relative paths against the profile directory (G_HOME_DIR)
    resolve_config_paths();
    
    if (!G_CLI_VERBOSE_SET && strlen(G_CONFIG.logging_verbosity) > 0) {
        if (_stricmp(G_CONFIG.logging_verbosity, "none") == 0) {
            G_VERBOSE_LEVEL = 0;
        } else if (_stricmp(G_CONFIG.logging_verbosity, "low") == 0) {
            G_VERBOSE_LEVEL = 1;
        } else if (_stricmp(G_CONFIG.logging_verbosity, "medium") == 0) {
            G_VERBOSE_LEVEL = 1;
        } else if (_stricmp(G_CONFIG.logging_verbosity, "high") == 0) {
            G_VERBOSE_LEVEL = 2;
        } else if (_stricmp(G_CONFIG.logging_verbosity, "debug") == 0) {
            G_VERBOSE_LEVEL = 2;
        }
        char debug_msg[256];
        snprintf(debug_msg, sizeof(debug_msg), "Logging verbosity set from INI: %s (level %d)", G_CONFIG.logging_verbosity, G_VERBOSE_LEVEL);
        log_debug(debug_msg);
    }
    
    if (G_VERBOSE_LEVEL >= 1) {
        char debug_msg[256];
        snprintf(debug_msg, sizeof(debug_msg), "Game: %s", G_CONFIG.name);
        log_debug(debug_msg);
        snprintf(debug_msg, sizeof(debug_msg), "Executable: %s", G_CONFIG.executable);
        log_debug(debug_msg);
        snprintf(debug_msg, sizeof(debug_msg), "Directory: %s", G_CONFIG.directory);
        log_debug(debug_msg);
    }
    
    return 0;
}

// --- Post-load path resolution ---
void resolve_config_paths() {
    #define RESOLVE_FIELD(field) do { \
        char _resolved[MAX_PATH_LEN]; \
        resolve_path(G_CONFIG.field, _resolved, sizeof(_resolved)); \
        strncpy(G_CONFIG.field, _resolved, sizeof(G_CONFIG.field) - 1); \
    } while(0)
    
    RESOLVE_FIELD(controller_mapper_app);
    RESOLVE_FIELD(borderless_windowing_app);
    RESOLVE_FIELD(monitorapp);
    RESOLVE_FIELD(cloud_app);
    RESOLVE_FIELD(disc_mount_app);
    RESOLVE_FIELD(disc_unmount_app);
    RESOLVE_FIELD(audio_app_path);
    RESOLVE_FIELD(pre_launch_app_1);
    RESOLVE_FIELD(pre_launch_app_2);
    RESOLVE_FIELD(pre_launch_app_3);
    RESOLVE_FIELD(post_launch_app_1);
    RESOLVE_FIELD(post_launch_app_2);
    RESOLVE_FIELD(post_launch_app_3);
    RESOLVE_FIELD(just_after_launch_app);
    RESOLVE_FIELD(just_before_exit_app);
    RESOLVE_FIELD(player1_profile);
    RESOLVE_FIELD(player2_profile);
    RESOLVE_FIELD(desk_profile);
    RESOLVE_FIELD(monitor_game_config);
    RESOLVE_FIELD(monitor_desk_config);
    RESOLVE_FIELD(unborder_cfg);
    RESOLVE_FIELD(reborder_cfg);
    RESOLVE_FIELD(disc_mount_cfg);
    RESOLVE_FIELD(disc_unmount_cfg);
    RESOLVE_FIELD(audio_game_cfg);
    RESOLVE_FIELD(audio_desk_cfg);
    
    #undef RESOLVE_FIELD
}

// --- Process Management ---
BOOL run_process(const char* command, const char* working_dir, BOOL wait, PROCESS_INFORMATION* pi) {
    STARTUPINFOA si;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(pi, sizeof(*pi));

    char debug_msg[512];
    snprintf(debug_msg, sizeof(debug_msg), "run_process: command=\"%s\", working_dir=\"%s\", wait=%d", command, working_dir ? working_dir : "NULL", wait);
    log_debug(debug_msg);
    
    // CreateProcess needs a mutable command line string
    char* cmd_mutable = _strdup(command);
    if (cmd_mutable == NULL) {
        log_message("ERROR", "run_process: failed to duplicate command string");
        return FALSE;
    }

    DWORD creation_flags = 0;
    if (G_IS_ADMIN && !wait) {
        creation_flags = CREATE_NEW_CONSOLE;
    }
    
    BOOL success = CreateProcessA(NULL, cmd_mutable, NULL, NULL, FALSE, creation_flags, NULL, working_dir, &si, pi);
    free(cmd_mutable);
    
    if (success) {
        snprintf(debug_msg, sizeof(debug_msg), "run_process: CreateProcess succeeded (PID: %lu)", pi->dwProcessId);
        log_debug(debug_msg);
        
        if (wait) {
            WaitForSingleObject(pi->hProcess, INFINITE);
            DWORD exit_code = 0;
            if (GetExitCodeProcess(pi->hProcess, &exit_code)) {
                snprintf(debug_msg, sizeof(debug_msg), "run_process: process exited with code %lu", exit_code);
                log_debug(debug_msg);
            }
            CloseHandle(pi->hProcess);
            CloseHandle(pi->hThread);
        }
    } else {
        DWORD error = GetLastError();
        snprintf(debug_msg, sizeof(debug_msg), "run_process: CreateProcess failed (error: %lu)", error);
        log_message("ERROR", debug_msg);
    }
    
    return success;
}

void terminate_process_tree(DWORD pid) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) return;

    PROCESSENTRY32 pe;
    pe.dwSize = sizeof(PROCESSENTRY32);

    // First pass: collect child PIDs
    DWORD child_pids[256];
    int child_count = 0;
    
    if (Process32First(hSnapshot, &pe)) {
        do {
            if (pe.th32ParentProcessID == pid && child_count < 256) {
                child_pids[child_count++] = pe.th32ProcessID;
            }
        } while (Process32Next(hSnapshot, &pe));
    }
    
    CloseHandle(hSnapshot);

    // Terminate children first (recursive)
    for (int i = 0; i < child_count; i++) {
        terminate_process_tree(child_pids[i]);
    }

    // Terminate the parent process
    HANDLE hProcess = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
    if (hProcess) {
        TerminateProcess(hProcess, 0);
        CloseHandle(hProcess);
    }
}

void kill_process_by_name(const char* process_name) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) return;

    PROCESSENTRY32 pe;
    pe.dwSize = sizeof(PROCESSENTRY32);

    if (Process32First(hSnapshot, &pe)) {
        do {
            if (_stricmp(pe.szExeFile, process_name) == 0) {
                terminate_process_tree(pe.th32ProcessID);
            }
        } while (Process32Next(hSnapshot, &pe));
    }

    CloseHandle(hSnapshot);
}

// --- Taskbar Control ---
void set_taskbar_visibility(BOOL show) {
    if (!G_TASKBAR_HWND) {
        G_TASKBAR_HWND = FindWindowA("Shell_TrayWnd", NULL);
    }
    if (G_TASKBAR_HWND) {
        ShowWindow(G_TASKBAR_HWND, show ? SW_SHOW : SW_HIDE);
        if (!show) {
            G_TASKBAR_WAS_HIDDEN = TRUE;
        }
    }
}

// --- Action Functions ---
static void build_cm_cmd(char* cmd, size_t cmd_size, const char* app,
                          const char* app_opts, const char* app_args,
                          const char* profile_opts, const char* profile_args,
                          const char* profile, const char* player_num) {
    char opts[MAX_CMD_LEN], args[MAX_CMD_LEN];
    const char* use_opts = strlen(profile_opts) > 0 ? profile_opts : app_opts;
    const char* use_args = strlen(profile_args) > 0 ? profile_args : app_args;
    string_replace(opts, sizeof(opts), use_opts, "${P#}", player_num);
    string_replace(args, sizeof(args), use_args, "${P#}", player_num);
    snprintf(cmd, cmd_size, "\"%s\" %s \"%s\" %s", app, opts, profile, args);
}

void action_run_controller_mapper(int is_exit) {
    if (!G_CONFIG.controller_mapper_enabled) return;
    char cmd[MAX_CMD_LEN];
    const char* profile1;
    const char* profile2;
    PROCESS_INFORMATION pi;
    char debug_msg[512];
    
    snprintf(debug_msg, sizeof(debug_msg), "Controller Mapper: %s (exit=%d)", is_exit ? "exit sequence" : "launch sequence", is_exit);
    log_debug(debug_msg);
    
    if (is_exit) {
        action_kill_controller_mapper();
        if (strlen(G_CONFIG.controller_mapper_app) == 0 || strlen(G_CONFIG.desk_profile) == 0) {
            show_message("  - Controller Mapper or Desk Profile not configured/found.");
            return;
        }
        DWORD attribs = GetFileAttributesA(G_CONFIG.controller_mapper_app);
        if (attribs == INVALID_FILE_ATTRIBUTES) {
            show_message("  - Controller Mapper executable not found.");
            return;
        }
        attribs = GetFileAttributesA(G_CONFIG.desk_profile);
        if (attribs == INVALID_FILE_ATTRIBUTES) {
            show_message("  - Desk profile not found.");
            return;
        }
        profile1 = G_CONFIG.desk_profile;
        profile2 = G_CONFIG.desk_profile;
    } else {
        if (strlen(G_CONFIG.controller_mapper_app) == 0 || strlen(G_CONFIG.player1_profile) == 0) {
            show_message("  - Controller Mapper or P1 Profile not configured/found.");
            return;
        }
        DWORD attribs = GetFileAttributesA(G_CONFIG.controller_mapper_app);
        if (attribs == INVALID_FILE_ATTRIBUTES) {
            show_message("  - Controller Mapper executable not found.");
            return;
        }
        attribs = GetFileAttributesA(G_CONFIG.player1_profile);
        if (attribs == INVALID_FILE_ATTRIBUTES) {
            show_message("  - Player 1 profile not found.");
            return;
        }
        profile1 = G_CONFIG.player1_profile;
        profile2 = strlen(G_CONFIG.player2_profile) > 0 ? G_CONFIG.player2_profile : NULL;
    }

    if (is_exit) {
        // Exit: use desk profile options/arguments for both players
        build_cm_cmd(cmd, sizeof(cmd), G_CONFIG.controller_mapper_app,
                     G_CONFIG.controller_mapper_options, G_CONFIG.controller_mapper_arguments,
                     G_CONFIG.desk_profile_options, G_CONFIG.desk_profile_arguments,
                     profile1, "1");
        if (run_process(cmd, NULL, FALSE, &pi)) {
            add_tracked_process("controller_mapper", &pi);
        }
        build_cm_cmd(cmd, sizeof(cmd), G_CONFIG.controller_mapper_app,
                     G_CONFIG.controller_mapper_options, G_CONFIG.controller_mapper_arguments,
                     G_CONFIG.desk_profile_options, G_CONFIG.desk_profile_arguments,
                     profile2, "2");
        if (run_process(cmd, NULL, FALSE, &pi)) {
            add_tracked_process("controller_mapper", &pi);
        }
    } else {
        // Launch: use per-player profile options/arguments
        build_cm_cmd(cmd, sizeof(cmd), G_CONFIG.controller_mapper_app,
                     G_CONFIG.controller_mapper_options, G_CONFIG.controller_mapper_arguments,
                     G_CONFIG.player1_profile_options, G_CONFIG.player1_profile_arguments,
                     profile1, "1");
        if (run_process(cmd, NULL, FALSE, &pi)) {
            add_tracked_process("controller_mapper", &pi);
        }
        if (profile2) {
            build_cm_cmd(cmd, sizeof(cmd), G_CONFIG.controller_mapper_app,
                         G_CONFIG.controller_mapper_options, G_CONFIG.controller_mapper_arguments,
                         G_CONFIG.player2_profile_options, G_CONFIG.player2_profile_arguments,
                         profile2, "2");
            if (run_process(cmd, NULL, FALSE, &pi)) {
                add_tracked_process("controller_mapper", &pi);
            }
        }
    }
}

void action_kill_controller_mapper() {
    // Kill all tracked controller mapper processes (there may be multiple from P1/P2)
    TrackedProcess* tp;
    while ((tp = find_tracked_process("controller_mapper")) != NULL) {
        terminate_process_tree(tp->pi.dwProcessId);
        CloseHandle(tp->pi.hProcess);
        CloseHandle(tp->pi.hThread);
        remove_tracked_process("controller_mapper");
    }
    if (strlen(G_CONFIG.controller_mapper_app) > 0) {
        // Fallback: kill by name
        char* name = strrchr(G_CONFIG.controller_mapper_app, '\\');
        if (!name) name = strrchr(G_CONFIG.controller_mapper_app, '/');
        if (!name) name = G_CONFIG.controller_mapper_app;
        else name++;
        kill_process_by_name(name);
    }
}

void action_run_monitor_config_game() {
    if (!G_CONFIG.monitor_game_cfg_enabled) return;
    if (strlen(G_CONFIG.monitorapp) == 0 || strlen(G_CONFIG.monitor_game_config) == 0) {
        return;
    }
    
    DWORD attribs = GetFileAttributesA(G_CONFIG.monitorapp);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;
    
    attribs = GetFileAttributesA(G_CONFIG.monitor_game_config);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    const char* use_opts = strlen(G_CONFIG.monitor_game_config_options) > 0
                             ? G_CONFIG.monitor_game_config_options
                             : G_CONFIG.monitorapp_options;
    const char* use_args = strlen(G_CONFIG.monitor_game_config_arguments) > 0
                             ? G_CONFIG.monitor_game_config_arguments
                             : G_CONFIG.monitorapp_arguments;
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\" %s \"%s\" %s",
             G_CONFIG.monitorapp,
             use_opts,
             G_CONFIG.monitor_game_config,
             use_args);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, TRUE, &pi);
}

void action_run_monitor_config_desktop() {
    if (!G_CONFIG.monitor_desk_cfg_enabled) return;
    if (strlen(G_CONFIG.monitorapp) == 0 || strlen(G_CONFIG.monitor_desk_config) == 0) {
        return;
    }
    
    DWORD attribs = GetFileAttributesA(G_CONFIG.monitorapp);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;
    
    attribs = GetFileAttributesA(G_CONFIG.monitor_desk_config);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    const char* use_opts = strlen(G_CONFIG.monitor_desk_config_options) > 0
                             ? G_CONFIG.monitor_desk_config_options
                             : G_CONFIG.monitorapp_options;
    const char* use_args = strlen(G_CONFIG.monitor_desk_config_arguments) > 0
                             ? G_CONFIG.monitor_desk_config_arguments
                             : G_CONFIG.monitorapp_arguments;
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\" %s \"%s\" %s",
             G_CONFIG.monitorapp,
             use_opts,
             G_CONFIG.monitor_desk_config,
             use_args);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, TRUE, &pi);
}

void action_hide_taskbar() {
    if (G_CONFIG.hide_taskbar) {
        set_taskbar_visibility(FALSE);
    }
}

void action_show_taskbar() {
    set_taskbar_visibility(TRUE);
}

void action_run_borderless() {
    if (!G_CONFIG.borderless_windowing_enabled) return;
    if ((strcmp(G_CONFIG.borderless, "E") == 0 || strcmp(G_CONFIG.borderless, "K") == 0) &&
        strlen(G_CONFIG.borderless_windowing_app) > 0) {
        
        char debug_msg[512];
        snprintf(debug_msg, sizeof(debug_msg), "Borderless app: %s, options: %s, args: %s", G_CONFIG.borderless_windowing_app, G_CONFIG.borderless_options, G_CONFIG.borderless_arguments);
        log_debug(debug_msg);
        
        DWORD attribs = GetFileAttributesA(G_CONFIG.borderless_windowing_app);
        if (attribs == INVALID_FILE_ATTRIBUTES) {
            log_debug("Borderless app not found");
            return;
        }

        char cmd[MAX_CMD_LEN];
        snprintf(cmd, sizeof(cmd), "\"%s\" %s %s",
                 G_CONFIG.borderless_windowing_app,
                 G_CONFIG.borderless_options,
                 G_CONFIG.borderless_arguments);
        
        PROCESS_INFORMATION pi;
        if (run_process(cmd, NULL, FALSE, &pi)) {
            G_BORDERLESS_PROCESS = pi.hProcess;
            snprintf(debug_msg, sizeof(debug_msg), "Borderless process started (PID: %lu)", pi.dwProcessId);
            log_debug(debug_msg);
            // Don't add to tracked - we handle separately
            CloseHandle(pi.hThread);
        }
    }
}

void action_kill_borderless() {
    char debug_msg[256];
    
    if (G_CONFIG.terminate_borderless_on_exit && G_BORDERLESS_PROCESS) {
        DWORD pid = GetProcessId(G_BORDERLESS_PROCESS);
        snprintf(debug_msg, sizeof(debug_msg), "Terminating borderless process (PID: %lu)", pid);
        log_debug(debug_msg);
        terminate_process_tree(pid);
        CloseHandle(G_BORDERLESS_PROCESS);
        G_BORDERLESS_PROCESS = NULL;
    } else if (G_CONFIG.terminate_borderless_on_exit && strlen(G_CONFIG.borderless_windowing_app) > 0) {
        // Fallback: kill by name
        char* name = strrchr(G_CONFIG.borderless_windowing_app, '\\');
        if (!name) name = strrchr(G_CONFIG.borderless_windowing_app, '/');
        if (!name) name = G_CONFIG.borderless_windowing_app;
        else name++;
        snprintf(debug_msg, sizeof(debug_msg), "Killing borderless by name: %s", name);
        log_debug(debug_msg);
        kill_process_by_name(name);
    }
}

void action_run_cloud_sync() {
    if (strlen(G_CONFIG.cloud_app) == 0) return;
    
    DWORD attribs = GetFileAttributesA(G_CONFIG.cloud_app);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\" %s %s",
             G_CONFIG.cloud_app,
             G_CONFIG.cloud_app_options,
             G_CONFIG.cloud_app_arguments);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, TRUE, &pi);
}

void action_run_generic_app(const char* app_path, int wait, const char* options, const char* args) {
    if (strlen(app_path) == 0) return;
    
    char debug_msg[512];
    snprintf(debug_msg, sizeof(debug_msg), "action_run_generic_app: path='%s', wait=%d, options='%s', args='%s'", app_path, wait, options ? options : "", args ? args : "");
    log_debug(debug_msg);
    
    char resolved[MAX_PATH_LEN];
    resolve_path(app_path, resolved, sizeof(resolved));
    
    snprintf(debug_msg, sizeof(debug_msg), "Resolved path: '%s'", resolved);
    log_debug(debug_msg);
    
    DWORD attribs = GetFileAttributesA(resolved);
    if (attribs == INVALID_FILE_ATTRIBUTES) {
        snprintf(debug_msg, sizeof(debug_msg), "App not found: %s", resolved);
        log_message("ERROR", debug_msg);
        return;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\"", resolved);
    
    if (options && strlen(options) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, options, sizeof(cmd) - strlen(cmd) - 1);
    }
    if (args && strlen(args) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, args, sizeof(cmd) - strlen(cmd) - 1);
    }
    
    snprintf(debug_msg, sizeof(debug_msg), "Command: %s", cmd);
    log_debug(debug_msg);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, wait, &pi);
    if (!wait && pi.hProcess) {
        char name[MAX_NAME_LEN];
        strncpy(name, resolved, MAX_NAME_LEN - 1);
        add_tracked_process(name, &pi);
    }
}

void action_kill_game() {
    if (strlen(G_GAME_EXE_NAME) > 0) {
        char debug_msg[256];
        snprintf(debug_msg, sizeof(debug_msg), "Killing game by exe name: %s", G_GAME_EXE_NAME);
        log_debug(debug_msg);
        kill_process_by_name(G_GAME_EXE_NAME);
    } else if (strlen(G_CONFIG.executable) > 0) {
        char* name = strrchr(G_CONFIG.executable, '\\');
        if (!name) name = strrchr(G_CONFIG.executable, '/');
        if (!name) name = G_CONFIG.executable;
        else name++;
        kill_process_by_name(name);
    }
}

void action_kill_process_list() {
    if (!G_CONFIG.use_kill_list || strlen(G_CONFIG.kill_list) == 0) return;
    
    char list_copy[MAX_CMD_LEN];
    strncpy(list_copy, G_CONFIG.kill_list, sizeof(list_copy) - 1);
    list_copy[sizeof(list_copy) - 1] = '\0';
    
    char* context = NULL;
    char* token = strtok_s(list_copy, ",", &context);
    
    while (token != NULL) {
        trim_whitespace(token);
        if (strlen(token) > 0) {
            kill_process_by_name(token);
        }
        token = strtok_s(NULL, ",", &context);
    }
}

void action_mount_disc_with_app() {
    if (!G_CONFIG.disc_mount_enabled) { action_mount_iso(); return; }
    if (strlen(G_CONFIG.disc_mount_app) == 0 || strlen(G_CONFIG.iso_path) == 0) {
        // Fallback to native mount
        action_mount_iso();
        return;
    }
    
    char resolved_app[MAX_PATH_LEN];
    char resolved_iso[MAX_PATH_LEN];
    resolve_path(G_CONFIG.disc_mount_app, resolved_app, sizeof(resolved_app));
    resolve_path(G_CONFIG.iso_path, resolved_iso, sizeof(resolved_iso));
    
    DWORD attribs = GetFileAttributesA(resolved_app);
    if (attribs == INVALID_FILE_ATTRIBUTES) {
        action_mount_iso();
        return;
    }
    
    attribs = GetFileAttributesA(resolved_iso);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    show_message("Mounting disc with external app...");
    
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\"", resolved_app);
    
    if (strlen(G_CONFIG.disc_mount_options) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, G_CONFIG.disc_mount_options, sizeof(cmd) - strlen(cmd) - 1);
    }
    
    strncat(cmd, " \"", sizeof(cmd) - strlen(cmd) - 1);
    strncat(cmd, resolved_iso, sizeof(cmd) - strlen(cmd) - 1);
    strncat(cmd, "\"", sizeof(cmd) - strlen(cmd) - 1);
    
    if (strlen(G_CONFIG.disc_mount_arguments) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, G_CONFIG.disc_mount_arguments, sizeof(cmd) - strlen(cmd) - 1);
    }
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, G_CONFIG.disc_mount_wait, &pi);
    
    if (!G_CONFIG.disc_mount_wait) {
        SleepMs(2000);
    }
}

void action_unmount_disc_with_app() {
    if (strlen(G_CONFIG.disc_unmount_app) == 0 || strlen(G_CONFIG.iso_path) == 0) {
        // Fallback to native unmount
        action_unmount_iso();
        return;
    }
    
    char resolved_app[MAX_PATH_LEN];
    char resolved_iso[MAX_PATH_LEN];
    resolve_path(G_CONFIG.disc_unmount_app, resolved_app, sizeof(resolved_app));
    resolve_path(G_CONFIG.iso_path, resolved_iso, sizeof(resolved_iso));
    
    DWORD attribs = GetFileAttributesA(resolved_app);
    if (attribs == INVALID_FILE_ATTRIBUTES) {
        action_unmount_iso();
        return;
    }

    show_message("Unmounting disc with external app...");
    
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\"", resolved_app);
    
    if (strlen(G_CONFIG.disc_unmount_options) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, G_CONFIG.disc_unmount_options, sizeof(cmd) - strlen(cmd) - 1);
    }
    
    // Add --unmount flag
    strncat(cmd, " --unmount \"", sizeof(cmd) - strlen(cmd) - 1);
    strncat(cmd, resolved_iso, sizeof(cmd) - strlen(cmd) - 1);
    strncat(cmd, "\"", sizeof(cmd) - strlen(cmd) - 1);
    
    if (strlen(G_CONFIG.disc_unmount_arguments) > 0) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, G_CONFIG.disc_unmount_arguments, sizeof(cmd) - strlen(cmd) - 1);
    }
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, G_CONFIG.disc_unmount_wait, &pi);
}

void action_mount_iso() {
    if (strlen(G_CONFIG.iso_path) == 0) return;
    
    char resolved[MAX_PATH_LEN];
    resolve_path(G_CONFIG.iso_path, resolved, sizeof(resolved));
    
    DWORD attribs = GetFileAttributesA(resolved);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    show_message("Mounting ISO with native Windows...");
    
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), 
             "powershell -Command \"Mount-DiskImage -ImagePath '%s'\"", 
             resolved);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, TRUE, &pi);
    
    SleepMs(2000); // Give time for mount
}

void action_unmount_iso() {
    if (strlen(G_CONFIG.iso_path) == 0) return;
    
    char resolved[MAX_PATH_LEN];
    resolve_path(G_CONFIG.iso_path, resolved, sizeof(resolved));

    show_message("Unmounting ISO with native Windows...");
    
    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), 
             "powershell -Command \"Dismount-DiskImage -ImagePath '%s'\"", 
             resolved);
    
    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, TRUE, &pi);
}

void action_run_audio_game() {
    if (!G_CONFIG.audio_app_enabled) return;
    if (strlen(G_CONFIG.audio_app_path) == 0 || strlen(G_CONFIG.audio_game_cfg) == 0) {
        return;
    }
    DWORD attribs = GetFileAttributesA(G_CONFIG.audio_app_path);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;
    attribs = GetFileAttributesA(G_CONFIG.audio_game_cfg);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\" %s %s\"%s\"%s %s",
             G_CONFIG.audio_app_path,
             G_CONFIG.audio_app_options,
             G_CONFIG.audio_game_cfg_options,
             G_CONFIG.audio_game_cfg,
             G_CONFIG.audio_game_cfg_arguments,
             G_CONFIG.audio_app_arguments);

    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, G_CONFIG.audio_app_run_wait, &pi);
}

void action_run_audio_desktop() {
    if (!G_CONFIG.audio_app_enabled) return;
    if (strlen(G_CONFIG.audio_app_path) == 0 || strlen(G_CONFIG.audio_desk_cfg) == 0) {
        return;
    }
    DWORD attribs = GetFileAttributesA(G_CONFIG.audio_app_path);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;
    attribs = GetFileAttributesA(G_CONFIG.audio_desk_cfg);
    if (attribs == INVALID_FILE_ATTRIBUTES) return;

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "\"%s\" %s %s\"%s\"%s %s",
             G_CONFIG.audio_app_path,
             G_CONFIG.audio_app_options,
             G_CONFIG.audio_desk_cfg_options,
             G_CONFIG.audio_desk_cfg,
             G_CONFIG.audio_desk_cfg_arguments,
             G_CONFIG.audio_app_arguments);

    PROCESS_INFORMATION pi;
    run_process(cmd, NULL, G_CONFIG.audio_app_run_wait, &pi);
}

// --- Sequence Execution ---
void execute_action(const char* action, int is_exit_sequence) {
    char debug_msg[256];
    
    snprintf(debug_msg, sizeof(debug_msg), "Executing action: %s (exit_sequence=%d)", action, is_exit_sequence);
    log_debug(debug_msg);
    show_message(action);
    
    if (G_VERBOSE_LEVEL >= 2) {
        snprintf(debug_msg, sizeof(debug_msg), "Action: %s, Exit sequence: %s", action, is_exit_sequence ? "Yes" : "No");
        log_debug(debug_msg);
    }
    
    if (strcmp(action, "Kill-Game") == 0) {
        action_kill_game();
    } else if (strcmp(action, "Kill-List") == 0) {
        action_kill_process_list();
    } else if (strcmp(action, "Controller-Mapper") == 0) {
        action_run_controller_mapper(is_exit_sequence);
    } else if (strcmp(action, "Monitor-Config") == 0) {
        if (is_exit_sequence) {
            action_run_monitor_config_desktop();
        } else {
            action_run_monitor_config_game();
        }
    } else if (strcmp(action, "No-TB") == 0) {
        if (!is_exit_sequence) action_hide_taskbar();
    } else if (strcmp(action, "Taskbar") == 0) {
        if (is_exit_sequence) action_show_taskbar();
    } else if (strcmp(action, "Borderless") == 0) {
        if (is_exit_sequence) {
            action_kill_borderless();
        } else {
            action_run_borderless();
        }
    } else if (strcmp(action, "Cloud-Sync") == 0) {
        action_run_cloud_sync();
    } else if (strcmp(action, "mount-disc") == 0) {
        if (!is_exit_sequence) action_mount_disc_with_app();
    } else if (strcmp(action, "Unmount-disc") == 0) {
        if (is_exit_sequence) action_unmount_disc_with_app();
    } else if (strcmp(action, "RunAudio") == 0) {
        if (!is_exit_sequence) action_run_audio_game();
    } else if (strcmp(action, "ReturnAudio") == 0) {
        if (is_exit_sequence) action_run_audio_desktop();
    } else if (strcmp(action, "Pre1") == 0) {
        action_run_generic_app(G_CONFIG.pre_launch_app_1, G_CONFIG.pre_launch_app_1_wait, 
                              G_CONFIG.pre_launch_app_1_options, G_CONFIG.pre_launch_app_1_arguments);
    } else if (strcmp(action, "Pre2") == 0) {
        action_run_generic_app(G_CONFIG.pre_launch_app_2, G_CONFIG.pre_launch_app_2_wait,
                              G_CONFIG.pre_launch_app_2_options, G_CONFIG.pre_launch_app_2_arguments);
    } else if (strcmp(action, "Pre3") == 0) {
        action_run_generic_app(G_CONFIG.pre_launch_app_3, G_CONFIG.pre_launch_app_3_wait,
                              G_CONFIG.pre_launch_app_3_options, G_CONFIG.pre_launch_app_3_arguments);
    } else if (strcmp(action, "Post1") == 0) {
        action_run_generic_app(G_CONFIG.post_launch_app_1, G_CONFIG.post_launch_app_1_wait,
                              G_CONFIG.post_launch_app_1_options, G_CONFIG.post_launch_app_1_arguments);
    } else if (strcmp(action, "Post2") == 0) {
        action_run_generic_app(G_CONFIG.post_launch_app_2, G_CONFIG.post_launch_app_2_wait,
                              G_CONFIG.post_launch_app_2_options, G_CONFIG.post_launch_app_2_arguments);
    } else if (strcmp(action, "Post3") == 0) {
        action_run_generic_app(G_CONFIG.post_launch_app_3, G_CONFIG.post_launch_app_3_wait,
                              G_CONFIG.post_launch_app_3_options, G_CONFIG.post_launch_app_3_arguments);
    } else if (strcmp(action, "JustAfterLaunch") == 0) {
        action_run_generic_app(G_CONFIG.just_after_launch_app, G_CONFIG.just_after_launch_wait,
                              G_CONFIG.just_after_launch_options, G_CONFIG.just_after_launch_arguments);
    } else if (strcmp(action, "JustBeforeExit") == 0) {
        action_run_generic_app(G_CONFIG.just_before_exit_app, G_CONFIG.just_before_exit_wait,
                              G_CONFIG.just_before_exit_options, G_CONFIG.just_before_exit_arguments);
    } else {
        char msg[256];
        snprintf(msg, sizeof(msg), "  - Unknown action: %s", action);
        show_message(msg);
    }
}

void execute_sequence(const char* sequence_str, int is_exit_sequence) {
    if (strlen(sequence_str) == 0) return;
    
    char debug_msg[256];
    snprintf(debug_msg, sizeof(debug_msg), "Starting %s sequence", is_exit_sequence ? "exit" : "launch");
    log_debug(debug_msg);
    
    char* sequence_copy = _strdup(sequence_str);
    if (sequence_copy == NULL) return;

    char* context = NULL;
    char* token = strtok_s(sequence_copy, ",", &context);
    int action_num = 0;

    while (token != NULL) {
        trim_whitespace(token);
        if (strlen(token) > 0) {
            action_num++;
            snprintf(debug_msg, sizeof(debug_msg), "Sequence action %d: %s", action_num, token);
            log_debug(debug_msg);
            execute_action(token, is_exit_sequence);
        }
        token = strtok_s(NULL, ",", &context);
    }
    
    snprintf(debug_msg, sizeof(debug_msg), "Completed %s sequence (%d actions)", is_exit_sequence ? "exit" : "launch", action_num);
    log_debug(debug_msg);

    free(sequence_copy);
}

void run_game_process() {
    show_message("Running game...");
    
    char debug_msg[512];
    char full_exe_path[MAX_PATH_LEN];
    
    snprintf(debug_msg, sizeof(debug_msg), "Game executable: '%s'", G_CONFIG.executable);
    log_debug(debug_msg);
    
    snprintf(debug_msg, sizeof(debug_msg), "Game directory: '%s'", G_CONFIG.directory);
    log_debug(debug_msg);
    
    snprintf(debug_msg, sizeof(debug_msg), "Elevation requested: %s", G_CONFIG.run_as_admin ? "Administrator" : "Standard");
    log_debug(debug_msg);
    
    if (strlen(G_CONFIG.executable) == 0) {
        show_message("No game executable configured.");
        log_message("ERROR", "Game.ini has empty 'executable' field in [Game] section");
        return;
    }
    
    // Build full path to executable if it's not already absolute
    if (strchr(G_CONFIG.executable, ':') != NULL || 
        (G_CONFIG.executable[0] == '\\' && G_CONFIG.executable[1] == '\\')) {
        // Already an absolute path (has drive letter or UNC path)
        strncpy(full_exe_path, G_CONFIG.executable, sizeof(full_exe_path) - 1);
        full_exe_path[sizeof(full_exe_path) - 1] = '\0';
    } else {
        // Relative path - combine with directory
        if (strlen(G_CONFIG.directory) > 0) {
            snprintf(full_exe_path, sizeof(full_exe_path), "%s\\%s", 
                     G_CONFIG.directory, G_CONFIG.executable);
        } else {
            strncpy(full_exe_path, G_CONFIG.executable, sizeof(full_exe_path) - 1);
            full_exe_path[sizeof(full_exe_path) - 1] = '\0';
        }
    }
    
    snprintf(debug_msg, sizeof(debug_msg), "Full executable path: '%s'", full_exe_path);
    log_debug(debug_msg);
    
    // Check if file exists
    DWORD attribs = GetFileAttributesA(full_exe_path);
    if (attribs == INVALID_FILE_ATTRIBUTES) {
        snprintf(debug_msg, sizeof(debug_msg), "ERROR: Executable not found: %s", full_exe_path);
        log_message("ERROR", debug_msg);
        show_message("Game executable not found!");
        return;
    }
    
    const char* working_dir = strlen(G_CONFIG.directory) > 0 ? G_CONFIG.directory : NULL;
    
    if (G_CONFIG.run_as_admin) {
        snprintf(debug_msg, sizeof(debug_msg), "Launching as admin: %s", full_exe_path);
        log_debug(debug_msg);
        
        if (working_dir) {
            snprintf(debug_msg, sizeof(debug_msg), "Working directory: %s", working_dir);
            log_debug(debug_msg);
        }
        
        HINSTANCE result = ShellExecuteA(NULL, "runas", full_exe_path, NULL, working_dir, SW_SHOWNORMAL);
        int result_code = (int)(intptr_t)result;
        
        snprintf(debug_msg, sizeof(debug_msg), "ShellExecute returned: %d", result_code);
        log_debug(debug_msg);
        
        if (result_code <= 32) {
            const char* error_desc = "Unknown error";
            switch (result_code) {
                case 0: error_desc = "Out of memory or resources"; break;
                case ERROR_FILE_NOT_FOUND: error_desc = "File not found"; break;
                case ERROR_PATH_NOT_FOUND: error_desc = "Path not found"; break;
                case ERROR_BAD_FORMAT: error_desc = "Invalid .exe file"; break;
                case SE_ERR_ACCESSDENIED: error_desc = "Access denied"; break;
                case SE_ERR_ASSOCINCOMPLETE: error_desc = "File association incomplete"; break;
                case SE_ERR_DDEBUSY: error_desc = "DDE busy"; break;
                case SE_ERR_DDEFAIL: error_desc = "DDE transaction failed"; break;
                case SE_ERR_DDETIMEOUT: error_desc = "DDE timeout"; break;
                case SE_ERR_DLLNOTFOUND: error_desc = "DLL not found"; break;
                case SE_ERR_NOASSOC: error_desc = "No file association"; break;
                case SE_ERR_OOM: error_desc = "Out of memory"; break;
                case SE_ERR_SHARE: error_desc = "Sharing violation"; break;
            }
            snprintf(debug_msg, sizeof(debug_msg), "ShellExecute failed with code %d: %s", result_code, error_desc);
            log_message("ERROR", debug_msg);
            show_message("Failed to launch game as administrator.");
            return;
        }
        log_message("INFO", "Game launched as administrator (process tracking unavailable)");
        G_GAME_PROCESS_INFO.hProcess = NULL;
        
        // Extract exe name for fallback process tracking
        char* exe_name = strrchr(G_CONFIG.executable, '\\');
        if (!exe_name) exe_name = strrchr(G_CONFIG.executable, '/');
        if (!exe_name) exe_name = G_CONFIG.executable;
        else exe_name++;
        strncpy(G_GAME_EXE_NAME, exe_name, MAX_NAME_LEN - 1);
        log_debug("Game exe name for fallback tracking saved");
    } else {
        char cmd[MAX_CMD_LEN];
        snprintf(cmd, sizeof(cmd), "\"%s\"", full_exe_path);
        
        snprintf(debug_msg, sizeof(debug_msg), "Launching: %s", cmd);
        log_debug(debug_msg);
        
        if (working_dir) {
            snprintf(debug_msg, sizeof(debug_msg), "Working directory: %s", working_dir);
            log_debug(debug_msg);
        }
        
        if (!run_process(cmd, working_dir, FALSE, &G_GAME_PROCESS_INFO)) {
            DWORD error = GetLastError();
            snprintf(debug_msg, sizeof(debug_msg), "CreateProcess failed with error code: %lu", error);
            log_message("ERROR", debug_msg);
            show_message("Failed to launch game.");
        } else {
            snprintf(debug_msg, sizeof(debug_msg), "Game process started successfully (PID: %lu)", G_GAME_PROCESS_INFO.dwProcessId);
            log_message("INFO", debug_msg);
        }
    }
}

// --- Admin Check ---
BOOL check_admin() {
    BOOL is_admin = FALSE;
    PSID admin_group = NULL;
    SID_IDENTIFIER_AUTHORITY nt_authority = SECURITY_NT_AUTHORITY;
    
    if (AllocateAndInitializeSid(&nt_authority, 2, SECURITY_BUILTIN_DOMAIN_RID,
                                  DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &admin_group)) {
        CheckTokenMembership(NULL, admin_group, &is_admin);
        FreeSid(admin_group);
    }
    
    return is_admin;
}

// --- Instance Management ---
BOOL check_instances() {
    if (strlen(G_PID_FILE) == 0) return TRUE;
    
    // Check if PID file exists
    FILE* pid_file = fopen(G_PID_FILE, "r");
    if (pid_file) {
        DWORD old_pid = 0;
        if (fscanf(pid_file, "%lu", &old_pid) == 1) {
            fclose(pid_file);
            
            // Check if process is still running
            HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, old_pid);
            if (hProcess) {
                DWORD exit_code;
                if (GetExitCodeProcess(hProcess, &exit_code) && exit_code == STILL_ACTIVE) {
                    CloseHandle(hProcess);
                    show_message("Another instance is already running.");
                    return FALSE;
                }
                CloseHandle(hProcess);
            }
        } else {
            fclose(pid_file);
        }
    }
    
    // Write our PID
    write_pid_file();
    return TRUE;
}

void write_pid_file() {
    if (strlen(G_PID_FILE) == 0) return;
    
    FILE* pid_file = fopen(G_PID_FILE, "w");
    if (pid_file) {
        fprintf(pid_file, "%lu", GetCurrentProcessId());
        fclose(pid_file);
    }
}

void cleanup_pid_file() {
    if (strlen(G_PID_FILE) == 0) return;
    DeleteFileA(G_PID_FILE);
}

void ensure_cleanup() {
    show_message("Ensuring cleanup...");
    
    if (G_TASKBAR_WAS_HIDDEN) {
        action_show_taskbar();
    }
    
    kill_all_tracked_processes();
    
    if (G_BORDERLESS_PROCESS) {
        CloseHandle(G_BORDERLESS_PROCESS);
        G_BORDERLESS_PROCESS = NULL;
    }
    
    cleanup_pid_file();
}

// --- Main Entry Point ---
int main(int argc, char* argv[]) {
    // Parse verbose flags FIRST to determine if we need a console
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0) {
            G_VERBOSE_LEVEL = 1;
            G_CLI_VERBOSE_SET = 1;
        } else if (strcmp(argv[i], "-vv") == 0 || strcmp(argv[i], "-vvv") == 0) {
            G_VERBOSE_LEVEL = 2;
            G_CLI_VERBOSE_SET = 1;
        } else if (strncmp(argv[i], "-v", 2) == 0) {
            int count = 0;
            for (const char* p = argv[i] + 1; *p == 'v'; p++) {
                count++;
            }
            if (count > 0) {
                G_VERBOSE_LEVEL = (count >= 2) ? 2 : 1;
                G_CLI_VERBOSE_SET = 1;
            }
        }
    }
    
    // Allocate console only if verbose mode is enabled
    if (G_VERBOSE_LEVEL > 0) {
        AllocConsole();
        #ifdef _MSC_VER
        // MSVC version
        FILE* dummy;
        freopen_s(&dummy, "CONOUT$", "w", stdout);
        freopen_s(&dummy, "CONOUT$", "w", stderr);
        #else
        // MinGW version
        freopen("CONOUT$", "w", stdout);
        freopen("CONOUT$", "w", stderr);
        #endif
    }
    
    if (argc < 2) {
        if (G_VERBOSE_LEVEL > 0) {
            printf("Usage: launcher.exe <path_to_shortcut> [-v|-vv|-vvv]\n");
            printf("  -v    Verbose output (show INFO and DEBUG messages)\n");
            printf("  -vv   Very verbose output (include timestamps)\n");
            printf("  -vvv  Maximum verbosity (same as -vv)\n");
        } else {
            MessageBoxA(NULL, 
                       "Usage: launcher.exe <path_to_shortcut> [-v|-vv|-vvv]\n\n"
                       "  -v    Verbose output\n"
                       "  -vv   Very verbose output\n"
                       "  -vvv  Maximum verbosity",
                       "Launcher - Usage",
                       MB_OK | MB_ICONINFORMATION);
        }
        SleepMs(2000);
        return 1;
    }

    // Reconstruct the full shortcut path from argv tokens.
    // Shortcut.exe crashes if parameters are double-quoted, so paths with spaces
    // arrive as separate argv tokens. Collect all non-flag tokens, then try
    // progressively shorter joins (longest first) until a valid path or .lnk is found.
    int path_start = 1;
    for (int i = 1; i < argc; i++) {
        if (argv[i][0] != '-') {
            path_start = i;
            break;
        }
    }
    char* tokens[MAX_NAME_LEN];
    int token_count = 0;
    for (int i = path_start; i < argc && argv[i][0] != '-'; i++) {
        tokens[token_count++] = argv[i];
    }
    char shortcut_path[MAX_PATH_LEN];
    shortcut_path[0] = '\0';
    for (int t = token_count; t >= 1; t--) {
        char candidate[MAX_PATH_LEN] = "";
        for (int j = 0; j < t; j++) {
            if (j > 0) strncat(candidate, " ", sizeof(candidate) - strlen(candidate) - 1);
            strncat(candidate, tokens[j], sizeof(candidate) - strlen(candidate) - 1);
        }
        DWORD attr = GetFileAttributesA(candidate);
        size_t len = strlen(candidate);
        int is_lnk = (len >= 4 && _stricmp(candidate + len - 4, ".lnk") == 0);
        if (attr != INVALID_FILE_ATTRIBUTES || is_lnk) {
            strncpy(shortcut_path, candidate, sizeof(shortcut_path) - 1);
            shortcut_path[sizeof(shortcut_path) - 1] = '\0';
            break;
        }
    }
    if (shortcut_path[0] == '\0') {
        strncpy(shortcut_path, tokens[0], sizeof(shortcut_path) - 1);
        shortcut_path[sizeof(shortcut_path) - 1] = '\0';
    }

    char ini_path[MAX_PATH_LEN];
    
    // Determine the path to Game.ini based on the shortcut path
    strncpy(ini_path, shortcut_path, MAX_PATH_LEN - 1);
    ini_path[MAX_PATH_LEN - 1] = '\0';
    
    if (G_VERBOSE_LEVEL > 0) {
        char debug_msg[512];
        snprintf(debug_msg, sizeof(debug_msg), "Shortcut path: %s", shortcut_path);
        printf("[DEBUG] %s\n", debug_msg);
    }
    
    // Remove filename to get directory
    char* last_slash = strrchr(ini_path, '\\');
    if (!last_slash) last_slash = strrchr(ini_path, '/');
    if (last_slash) {
        *(last_slash + 1) = '\0';
    }
    
    // Search for Game.ini case-insensitively in the shortcut directory
    char game_ini_path[MAX_PATH_LEN] = "";
    WIN32_FIND_DATAA find_data;
    char search_pattern[MAX_PATH_LEN];
    snprintf(search_pattern, sizeof(search_pattern), "%s*", ini_path);
    
    HANDLE hFind = FindFirstFileA(search_pattern, &find_data);
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (!(find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                if (_stricmp(find_data.cFileName, "Game.ini") == 0) {
                    snprintf(game_ini_path, sizeof(game_ini_path), "%s%s", ini_path, find_data.cFileName);
                    break;
                }
            }
        } while (FindNextFileA(hFind, &find_data));
        FindClose(hFind);
    }
    
    // If no Game.ini found, fall back so ini_path is still a file path (for proper error messages)
    if (strlen(game_ini_path) > 0) {
        strncpy(ini_path, game_ini_path, MAX_PATH_LEN - 1);
        ini_path[MAX_PATH_LEN - 1] = '\0';
    } else {
        strncat(ini_path, "Game.ini", MAX_PATH_LEN - strlen(ini_path) - 1);
    }
    
    if (G_VERBOSE_LEVEL > 0) {
        char debug_msg[512];
        snprintf(debug_msg, sizeof(debug_msg), "Game.ini path: %s", ini_path);
        printf("[DEBUG] %s\n", debug_msg);
    }
    
    // Set home directory
    strncpy(G_HOME_DIR, ini_path, MAX_PATH_LEN - 1);
    char* last_sep = strrchr(G_HOME_DIR, '\\');
    if (!last_sep) last_sep = strrchr(G_HOME_DIR, '/');
    if (last_sep) *last_sep = '\0';
    
    // Set PID file path
    snprintf(G_PID_FILE, sizeof(G_PID_FILE), "%s\\rjpids.ini", G_HOME_DIR);

    show_message("Launcher starting...");
    
    if (G_VERBOSE_LEVEL > 0) {
        char verbose_msg[128];
        snprintf(verbose_msg, sizeof(verbose_msg), "Verbose mode enabled (level %d)", G_VERBOSE_LEVEL);
        log_message("INFO", verbose_msg);
        printf("[INFO] Verbose mode enabled (level %d)\n", G_VERBOSE_LEVEL);
    }
    
    if (G_VERBOSE_LEVEL >= 2) {
        char debug_msg[128];
        snprintf(debug_msg, sizeof(debug_msg), "Elevation: %s", G_IS_ADMIN ? "Administrator" : "Standard User");
        log_debug(debug_msg);
    }
    
    // Check admin privileges
    G_IS_ADMIN = check_admin();
    if (G_IS_ADMIN) {
        show_message("Running with administrator privileges.");
    }
    
    // Check for other instances
    if (!check_instances()) {
        show_message("Another instance is already running. Exiting.");
        SleepMs(2000);
        return 1;
    }

    // Initialize the configuration struct with zeros
    memset(&G_CONFIG, 0, sizeof(GameConfiguration));
    memset(&G_GAME_PROCESS_INFO, 0, sizeof(PROCESS_INFORMATION));

    // Check if Game.ini exists
    if (GetFileAttributesA(ini_path) == INVALID_FILE_ATTRIBUTES) {
        char debug_msg[512];
        snprintf(debug_msg, sizeof(debug_msg), "Game.ini not found at: %s", ini_path);
        log_message("ERROR", debug_msg);
        show_message("Game.ini not found.");
        SleepMs(2000);
        return 1;
    }

    // Load configuration
    if (load_configuration(ini_path) != 0) {
        show_message("Failed to load configuration.");
        SleepMs(2000);
        return 1;
    }

    // Find taskbar window
    G_TASKBAR_HWND = FindWindowA("Shell_TrayWnd", NULL);

    // Initialize tray menu
    HINSTANCE hInstance = GetModuleHandle(NULL);
    if (!tray_init(hInstance, ini_path, shortcut_path)) {
        show_message("Warning: Tray menu initialization failed");
    }

    // Execute launch sequence
    execute_sequence(G_CONFIG.launch_sequence, 0);

    // Run the game
    run_game_process();

    // Wait for the game process to exit (if we have a handle)
    // Use a message loop so tray menu can receive events
    if (G_GAME_PROCESS_INFO.hProcess != NULL) {
        MSG msg;
        BOOL game_running = TRUE;
        char exit_debug[256];
        
        while (game_running) {
            // Check if game is still running
            DWORD exit_code;
            if (GetExitCodeProcess(G_GAME_PROCESS_INFO.hProcess, &exit_code)) {
                if (exit_code != STILL_ACTIVE) {
                    game_running = FALSE;
                    snprintf(exit_debug, sizeof(exit_debug), "Game process exited with code: %lu", exit_code);
                    log_debug(exit_debug);
                    break;
                }
            }
            
            // Process Windows messages (for tray menu)
            while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
                if (msg.message == WM_QUIT) {
                    game_running = FALSE;
                    break;
                }
                TranslateMessage(&msg);
                DispatchMessageA(&msg);
            }
            
            // Don't hog CPU
            SleepMs(100);
        }
        
        CloseHandle(G_GAME_PROCESS_INFO.hProcess);
        CloseHandle(G_GAME_PROCESS_INFO.hThread);
    } else {
        // No process handle (e.g., ShellExecute "runas") — poll by name
        MSG msg;
        HANDLE hSnapshot;
        PROCESSENTRY32 pe;
        BOOL game_running = TRUE;
        
        log_message("INFO", "Fallback process tracking enabled (by executable name)");
        char debug_msg[256];
        snprintf(debug_msg, sizeof(debug_msg), "Tracking process name: '%s'", G_GAME_EXE_NAME);
        log_debug(debug_msg);
        
        while (game_running) {
            game_running = FALSE;
            hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (hSnapshot != INVALID_HANDLE_VALUE) {
                pe.dwSize = sizeof(PROCESSENTRY32);
                if (Process32First(hSnapshot, &pe)) {
                    do {
                        if (_stricmp(pe.szExeFile, G_GAME_EXE_NAME) == 0) {
                            game_running = TRUE;
                            break;
                        }
                    } while (Process32Next(hSnapshot, &pe));
                }
                CloseHandle(hSnapshot);
            }
            
            // Process Windows messages (for tray menu)
            while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
                if (msg.message == WM_QUIT) {
                    game_running = FALSE;
                    break;
                }
                TranslateMessage(&msg);
                DispatchMessageA(&msg);
            }
            
            SleepMs(100);
        }
        
        log_message("INFO", "Game process exited (detected by name polling)");
    }

    // Execute exit sequence
    execute_sequence(G_CONFIG.exit_sequence, 1);

    // Final cleanup
    ensure_cleanup();
    
    // Cleanup tray menu
    tray_cleanup();
    
    show_message("Launcher finished.");
    return 0;
}