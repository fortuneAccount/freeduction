/**
 * tray_menu.c - System Tray Menu Implementation
 *
 * Windows-only implementation using native Win32 API.
 * No additional dependencies required.
 */

#include <windows.h>
#include <commctrl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compat.h"
#include "launcher_common.h"
#include "tray_menu.h"

// External references from launcher.c
extern GameConfiguration G_CONFIG;
extern PROCESS_INFORMATION G_GAME_PROCESS_INFO;
extern int G_VERBOSE_LEVEL;
extern void terminate_process_tree(DWORD pid);
extern void execute_sequence(const char* sequence_str, int is_exit_sequence);
extern void ensure_cleanup();
extern void action_kill_process_list();
extern void show_message(const char* message);
extern void log_message(const char* level, const char* message);

// Global tray menu instance
TrayMenu G_TRAY_MENU = {0};

// Window class name
static const char* TRAY_CLASS_NAME = "LauncherTrayWindow";

/**
 * Initialize the tray menu
 */
BOOL tray_init(HINSTANCE hInstance, const char* ini_path, const char* lnk_path) {
    // Register window class
    WNDCLASSEXA wc = {0};
    wc.cbSize = sizeof(WNDCLASSEXA);
    wc.lpfnWndProc = tray_wnd_proc;
    wc.hInstance = hInstance;
    wc.lpszClassName = TRAY_CLASS_NAME;
    
    if (!RegisterClassExA(&wc)) {
        log_message("ERROR", "Failed to register tray window class");
        return FALSE;
    }
    
    // Create hidden window for message handling
    G_TRAY_MENU.hwnd = CreateWindowExA(
        0,
        TRAY_CLASS_NAME,
        "Launcher Tray",
        0,
        0, 0, 0, 0,
        NULL,
        NULL,
        hInstance,
        NULL
    );
    
    if (!G_TRAY_MENU.hwnd) {
        log_message("ERROR", "Failed to create tray window");
        return FALSE;
    }
    
    // Store paths
    strncpy(G_TRAY_MENU.ini_path, ini_path, MAX_PATH_LEN - 1);
    strncpy(G_TRAY_MENU.lnk_path, lnk_path, MAX_PATH_LEN - 1);
    
    // Create tray icon
    ZeroMemory(&G_TRAY_MENU.nid, sizeof(NOTIFYICONDATAA));
    G_TRAY_MENU.nid.cbSize = sizeof(NOTIFYICONDATAA);
    G_TRAY_MENU.nid.hWnd = G_TRAY_MENU.hwnd;
    G_TRAY_MENU.nid.uID = 1;
    G_TRAY_MENU.nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    G_TRAY_MENU.nid.uCallbackMessage = WM_TRAYICON;
    
    // Load icon (try to load from file, fallback to default)
    char icon_path[MAX_PATH_LEN];
    GetModuleFileNameA(NULL, icon_path, MAX_PATH_LEN);
    char* last_slash = strrchr(icon_path, '\\');
    if (last_slash) {
        *(last_slash + 1) = '\0';
        strncat(icon_path, "..\\assets\\Joystick.ico", MAX_PATH_LEN - strlen(icon_path) - 1);
    }
    
    G_TRAY_MENU.nid.hIcon = (HICON)LoadImageA(
        NULL,
        icon_path,
        IMAGE_ICON,
        0, 0,
        LR_LOADFROMFILE | LR_DEFAULTSIZE
    );
    
    if (!G_TRAY_MENU.nid.hIcon) {
        // Fallback to application icon
        G_TRAY_MENU.nid.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    }
    
    // Set tooltip
    snprintf(G_TRAY_MENU.nid.szTip, sizeof(G_TRAY_MENU.nid.szTip), 
             "%s - Launcher", G_CONFIG.name);
    
    // Add tray icon
    if (!Shell_NotifyIconA(NIM_ADD, &G_TRAY_MENU.nid)) {
        log_message("ERROR", "Failed to add tray icon");
        DestroyWindow(G_TRAY_MENU.hwnd);
        return FALSE;
    }
    
    G_TRAY_MENU.running = TRUE;
    log_message("INFO", "Tray menu initialized");
    return TRUE;
}

/**
 * Cleanup tray menu
 */
void tray_cleanup() {
    if (G_TRAY_MENU.running) {
        Shell_NotifyIconA(NIM_DELETE, &G_TRAY_MENU.nid);
        
        if (G_TRAY_MENU.hmenu) {
            DestroyMenu(G_TRAY_MENU.hmenu);
        }
        
        if (G_TRAY_MENU.hwnd) {
            DestroyWindow(G_TRAY_MENU.hwnd);
        }
        
        G_TRAY_MENU.running = FALSE;
        log_message("INFO", "Tray menu cleaned up");
    }
}

/**
 * Window procedure for tray icon
 */
LRESULT CALLBACK tray_wnd_proc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_TRAYICON:
            if (lParam == WM_RBUTTONUP || lParam == WM_CONTEXTMENU) {
                tray_show_context_menu(hwnd);
            }
            break;
            
        case WM_COMMAND:
            switch (LOWORD(wParam)) {
                case ID_TRAY_RESTART:
                    tray_restart_launcher();
                    break;
                case ID_TRAY_STOP:
                    tray_stop_game();
                    break;
                case ID_TRAY_KILL:
                    tray_kill_all();
                    break;
                case ID_TRAY_DISPLAY:
                    tray_display_config();
                    break;
                case ID_TRAY_CHANGE:
                    tray_change_config();
                    break;
                case ID_TRAY_EXIT:
                    tray_exit_launcher();
                    break;
            }
            break;
            
        case WM_DESTROY:
            PostQuitMessage(0);
            break;
            
        default:
            return DefWindowProcA(hwnd, msg, wParam, lParam);
    }
    return 0;
}

/**
 * Show context menu
 */
void tray_show_context_menu(HWND hwnd) {
    POINT pt;
    GetCursorPos(&pt);
    
    // Create popup menu
    HMENU hmenu = CreatePopupMenu();
    if (!hmenu) return;
    
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_RESTART, "Restart");
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_STOP, "Stop");
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_KILL, "Kill");
    AppendMenuA(hmenu, MF_SEPARATOR, 0, NULL);
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_DISPLAY, "Display Config");
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_CHANGE, "Change Config");
    AppendMenuA(hmenu, MF_SEPARATOR, 0, NULL);
    AppendMenuA(hmenu, MF_STRING, ID_TRAY_EXIT, "Exit Launcher");
    
    // Required for popup menu to work correctly
    SetForegroundWindow(hwnd);
    
    TrackPopupMenu(
        hmenu,
        TPM_BOTTOMALIGN | TPM_LEFTALIGN,
        pt.x, pt.y,
        0,
        hwnd,
        NULL
    );
    
    DestroyMenu(hmenu);
}

/**
 * Restart launcher
 */
void tray_restart_launcher() {
    log_message("INFO", "Restart requested from tray menu");
    
    if (strlen(G_TRAY_MENU.lnk_path) > 0) {
        // Stop current game
        tray_stop_game();
        
        // Restart launcher
        ShellExecuteA(NULL, "open", G_TRAY_MENU.lnk_path, NULL, NULL, SW_SHOWNORMAL);
        log_message("INFO", "Launcher restarted");
        
        // Exit current instance
        tray_exit_launcher();
    } else {
        show_message("No launcher link file found for restart");
    }
}

/**
 * Stop game using exit sequences
 */
void tray_stop_game() {
    log_message("INFO", "Stop requested from tray menu");
    
    // Execute exit sequence
    execute_sequence(G_CONFIG.exit_sequence, 1);
    
    // Terminate game process
    if (G_GAME_PROCESS_INFO.hProcess) {
        terminate_process_tree(G_GAME_PROCESS_INFO.dwProcessId);
        CloseHandle(G_GAME_PROCESS_INFO.hProcess);
        CloseHandle(G_GAME_PROCESS_INFO.hThread);
        ZeroMemory(&G_GAME_PROCESS_INFO, sizeof(PROCESS_INFORMATION));
        log_message("INFO", "Game process terminated");
    }
}

/**
 * Force kill all processes
 */
void tray_kill_all() {
    log_message("INFO", "Kill all requested from tray menu");
    
    // Kill game process
    if (G_GAME_PROCESS_INFO.hProcess) {
        TerminateProcess(G_GAME_PROCESS_INFO.hProcess, 0);
        CloseHandle(G_GAME_PROCESS_INFO.hProcess);
        CloseHandle(G_GAME_PROCESS_INFO.hThread);
        ZeroMemory(&G_GAME_PROCESS_INFO, sizeof(PROCESS_INFORMATION));
        log_message("INFO", "Game process killed");
    }
    
    // Kill processes in kill list
    action_kill_process_list();
    
    // Cleanup and exit
    ensure_cleanup();
    tray_exit_launcher();
}

/**
 * Display configuration dialog
 */
void tray_display_config() {
    log_message("INFO", "Display config requested from tray menu");
    
    DialogBoxParamA(
        GetModuleHandle(NULL),
        MAKEINTRESOURCEA(1),  // We'll create this dynamically
        G_TRAY_MENU.hwnd,
        display_config_dlg_proc,
        (LPARAM)G_TRAY_MENU.ini_path
    );
}

/**
 * Change configuration dialog
 */
void tray_change_config() {
    log_message("INFO", "Change config requested from tray menu");
    
    // Use advanced config editor
    extern BOOL show_config_editor(HWND parent, const char* ini_path);
    
    if (show_config_editor(NULL, G_TRAY_MENU.ini_path)) {
        // Config was saved
        int result = MessageBoxA(NULL,
                               "Configuration has been saved.\n\n"
                               "Would you like to restart the launcher to apply changes?",
                               "Configuration Saved",
                               MB_YESNO | MB_ICONQUESTION);
        
        if (result == IDYES) {
            log_message("INFO", "Restarting launcher to apply configuration changes");
            tray_restart_launcher();
        }
    }
}

/**
 * Exit launcher
 */
void tray_exit_launcher() {
    log_message("INFO", "Exit requested from tray menu");
    
    // Stop game first
    tray_stop_game();
    
    // Cleanup tray icon itself
    tray_cleanup();
    
    // Post a quit message to the main message loop to allow graceful shutdown
    PostQuitMessage(0);
}

/**
 * Display config dialog procedure
 */
INT_PTR CALLBACK display_config_dlg_proc(HWND hwndDlg, UINT message, WPARAM wParam, LPARAM lParam) {
    static char* config_text = NULL;
    
    switch (message) {
        case WM_INITDIALOG: {
            // Read config file
            const char* ini_path = (const char*)lParam;
            FILE* f = fopen(ini_path, "r");
            if (f) {
                fseek(f, 0, SEEK_END);
                long size = ftell(f);
                fseek(f, 0, SEEK_SET);
                
                config_text = (char*)malloc(size + 1);
                if (config_text) {
                    fread(config_text, 1, size, f);
                    config_text[size] = '\0';
                    
                    // Set text in edit control (ID 101)
                    SetDlgItemTextA(hwndDlg, 101, config_text);
                }
                fclose(f);
            }
            
            SetWindowTextA(hwndDlg, "Current Configuration");
            return TRUE;
        }
        
        case WM_COMMAND:
            if (LOWORD(wParam) == IDOK || LOWORD(wParam) == IDCANCEL) {
                if (config_text) {
                    free(config_text);
                    config_text = NULL;
                }
                EndDialog(hwndDlg, LOWORD(wParam));
                return TRUE;
            }
            break;
            
        case WM_CLOSE:
            if (config_text) {
                free(config_text);
                config_text = NULL;
            }
            EndDialog(hwndDlg, 0);
            return TRUE;
    }
    return FALSE;
}

/**
 * Create display config dialog template dynamically
 */
HWND create_display_config_dialog(HWND parent, const char* ini_path) {
    // Create a simple dialog with a multiline edit control
    HWND hwnd = CreateWindowExA(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        "STATIC",
        "Current Configuration",
        WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
        CW_USEDEFAULT, CW_USEDEFAULT, 600, 400,
        parent,
        NULL,
        GetModuleHandle(NULL),
        NULL
    );
    
    if (!hwnd) return NULL;
    
    // Create multiline edit control
    HWND edit = CreateWindowExA(
        WS_EX_CLIENTEDGE,
        "EDIT",
        "",
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_HSCROLL | 
        ES_MULTILINE | ES_AUTOVSCROLL | ES_AUTOHSCROLL | ES_READONLY,
        10, 10, 570, 320,
        hwnd,
        (HMENU)101,
        GetModuleHandle(NULL),
        NULL
    );
    
    // Set font
    HFONT hFont = CreateFontA(
        14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        DEFAULT_QUALITY, FIXED_PITCH | FF_MODERN, "Courier New"
    );
    SendMessage(edit, WM_SETFONT, (WPARAM)hFont, TRUE);
    
    // Read and display config
    FILE* f = fopen(ini_path, "r");
    if (f) {
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        fseek(f, 0, SEEK_SET);
        
        char* text = (char*)malloc(size + 1);
        if (text) {
            fread(text, 1, size, f);
            text[size] = '\0';
            SetWindowTextA(edit, text);
            free(text);
        }
        fclose(f);
    }
    
    // Create Close button
    CreateWindowExA(
        0,
        "BUTTON",
        "Close",
        WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON,
        250, 340, 100, 30,
        hwnd,
        (HMENU)IDOK,
        GetModuleHandle(NULL),
        NULL
    );
    
    return hwnd;
}
