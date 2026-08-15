/**
 * tray_menu.h - System Tray Menu for C Launcher
 *
 * Provides a system tray icon with context menu using only Windows API.
 * No additional dependencies required.
 */

#ifndef TRAY_MENU_H
#define TRAY_MENU_H

#include <windows.h>
#include "launcher_common.h"

// Tray menu IDs
#define WM_TRAYICON (WM_USER + 1)
#define ID_TRAY_RESTART 1001
#define ID_TRAY_STOP 1002
#define ID_TRAY_KILL 1003
#define ID_TRAY_DISPLAY 1004
#define ID_TRAY_CHANGE 1005
#define ID_TRAY_EXIT 1006

// Tray menu structure
typedef struct {
    HWND hwnd;
    NOTIFYICONDATAA nid;
    HMENU hmenu;
    BOOL running;
    char ini_path[MAX_PATH_LEN];
    char lnk_path[MAX_PATH_LEN];
} TrayMenu;

// Global tray menu instance
extern TrayMenu G_TRAY_MENU;

// Function prototypes
BOOL tray_init(HINSTANCE hInstance, const char* ini_path, const char* lnk_path);
void tray_cleanup();
LRESULT CALLBACK tray_wnd_proc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
void tray_show_context_menu(HWND hwnd);
void tray_restart_launcher();
void tray_stop_game();
void tray_kill_all();
void tray_display_config();
void tray_change_config();
void tray_exit_launcher();

// Dialog procedures
INT_PTR CALLBACK display_config_dlg_proc(HWND hwndDlg, UINT message, WPARAM wParam, LPARAM lParam);
INT_PTR CALLBACK change_config_dlg_proc(HWND hwndDlg, UINT message, WPARAM wParam, LPARAM lParam);

#endif // TRAY_MENU_H
