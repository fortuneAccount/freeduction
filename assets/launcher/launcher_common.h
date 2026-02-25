/**
 * launcher_common.h - Shared constants and structures for launcher
 *
 * This header contains constants and type definitions shared between
 * launcher.c and tray_menu.c
 */

#ifndef LAUNCHER_COMMON_H
#define LAUNCHER_COMMON_H

#include <windows.h>

// --- Constants ---
#define MAX_PATH_LEN 1024
#define MAX_SEQUENCE_LEN 2048
#define MAX_NAME_LEN 256
#define MAX_CMD_LEN 4096
#define LOG_BUFFER_SIZE 512

// --- Global Configuration Struct ---
typedef struct {
    // [Game]
    char executable[MAX_PATH_LEN];
    char directory[MAX_PATH_LEN];
    char name[MAX_NAME_LEN];
    char iso_path[MAX_PATH_LEN];

    // [Paths]
    char controller_mapper_app[MAX_PATH_LEN];
    char controller_mapper_options[MAX_CMD_LEN];
    char controller_mapper_arguments[MAX_CMD_LEN];
    char borderless_windowing_app[MAX_PATH_LEN];
    char borderless_options[MAX_CMD_LEN];
    char borderless_arguments[MAX_CMD_LEN];
    char multimonitor_tool[MAX_PATH_LEN];
    char multimonitor_options[MAX_CMD_LEN];
    char multimonitor_arguments[MAX_CMD_LEN];
    char player1_profile[MAX_PATH_LEN];
    char player2_profile[MAX_PATH_LEN];
    char mediacenter_profile[MAX_PATH_LEN];
    char mm_game_config[MAX_PATH_LEN];
    char mm_desktop_config[MAX_PATH_LEN];
    char cloud_app[MAX_PATH_LEN];
    char cloud_app_options[MAX_CMD_LEN];
    char cloud_app_arguments[MAX_CMD_LEN];
    
    // Disc mounting
    char disc_mount_app[MAX_PATH_LEN];
    char disc_mount_options[MAX_CMD_LEN];
    char disc_mount_arguments[MAX_CMD_LEN];
    int disc_mount_wait;
    char disc_unmount_app[MAX_PATH_LEN];
    char disc_unmount_options[MAX_CMD_LEN];
    char disc_unmount_arguments[MAX_CMD_LEN];
    int disc_unmount_wait;

    // [Options]
    int run_as_admin;
    int hide_taskbar;
    char borderless[4];
    int use_kill_list;
    int terminate_borderless_on_exit;
    char kill_list[MAX_CMD_LEN];
    int backup_saves;
    int max_backups;

    // [PreLaunch]
    char pre_launch_app_1[MAX_PATH_LEN];
    char pre_launch_app_1_options[MAX_CMD_LEN];
    char pre_launch_app_1_arguments[MAX_CMD_LEN];
    char pre_launch_app_2[MAX_PATH_LEN];
    char pre_launch_app_2_options[MAX_CMD_LEN];
    char pre_launch_app_2_arguments[MAX_CMD_LEN];
    char pre_launch_app_3[MAX_PATH_LEN];
    char pre_launch_app_3_options[MAX_CMD_LEN];
    char pre_launch_app_3_arguments[MAX_CMD_LEN];
    int pre_launch_app_1_wait;
    int pre_launch_app_2_wait;
    int pre_launch_app_3_wait;

    // [PostLaunch]
    char post_launch_app_1[MAX_PATH_LEN];
    char post_launch_app_1_options[MAX_CMD_LEN];
    char post_launch_app_1_arguments[MAX_CMD_LEN];
    char post_launch_app_2[MAX_PATH_LEN];
    char post_launch_app_2_options[MAX_CMD_LEN];
    char post_launch_app_2_arguments[MAX_CMD_LEN];
    char post_launch_app_3[MAX_PATH_LEN];
    char post_launch_app_3_options[MAX_CMD_LEN];
    char post_launch_app_3_arguments[MAX_CMD_LEN];
    char just_after_launch_app[MAX_PATH_LEN];
    char just_after_launch_options[MAX_CMD_LEN];
    char just_after_launch_arguments[MAX_CMD_LEN];
    char just_before_exit_app[MAX_PATH_LEN];
    char just_before_exit_options[MAX_CMD_LEN];
    char just_before_exit_arguments[MAX_CMD_LEN];
    int post_launch_app_1_wait;
    int post_launch_app_2_wait;
    int post_launch_app_3_wait;
    int just_after_launch_wait;
    int just_before_exit_wait;

    // [Sequences]
    char launch_sequence[MAX_SEQUENCE_LEN];
    char exit_sequence[MAX_SEQUENCE_LEN];

} GameConfiguration;

#endif // LAUNCHER_COMMON_H
