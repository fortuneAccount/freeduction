/**
 * config_editor.c - Advanced Configuration Editor for Game.ini
 * 
 * Full GUI implementation with parity to Python version
 */

#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "compat.h"
#include "launcher_common.h"
#include "inih/ini.h"

// External function from launcher.c
extern void log_message(const char* level, const char* message);

#define MAX_CONTROLS 150
#define CONTROL_HEIGHT 20        // Reduced from 24 for compact layout
#define CONTROL_SPACING 2        // Minimal spacing between controls
#define LABEL_WIDTH 100          // Reduced from 110
#define EDIT_WIDTH 400           // Increased from 380
#define BUTTON_WIDTH 30
#define DIALOG_WIDTH 650
#define DIALOG_HEIGHT 440
#define SCROLL_WIDTH 20
#define ACTION_BTN_WIDTH 50      // Width for action buttons
#define ACTION_BTN_HEIGHT 25     // Height for action buttons

// Control IDs - New button bar
#define IDC_IMPORT_BTN 2001
#define IDC_RESET_BTN 2002
#define IDC_RELOAD_BTN 2003
#define IDC_SAVE_BTN 2004
#define IDC_EXPORT_BTN 2005
#define IDC_OK_BTN 2006
#define IDC_SCROLL_VERT 2010
#define IDC_CONTROL_BASE 3000

// Control types
typedef enum {
    CTRL_TEXT,
    CTRL_PATH_FILE,
    CTRL_PATH_FOLDER,
    CTRL_BOOL,
    CTRL_LIST
} ControlType;

// Control structure
typedef struct {
    char section[64];
    char key[64];
    char value[MAX_CMD_LEN];
    ControlType type;
    int y_pos;
    HWND label;
    HWND edit;
    HWND button;
    HWND combo;
    HWND add_btn;
    HWND del_btn;
    int id;
} ConfigControl;

// Dialog data
typedef struct {
    char ini_path[MAX_PATH_LEN];
    char original_ini_path[MAX_PATH_LEN];  // For Reset functionality
    ConfigControl controls[MAX_CONTROLS];
    int control_count;
    HWND dialog;
    HWND content_area;
    int content_height;
    int scroll_pos;
    BOOL modified;  // Track if changes have been made
} ConfigEditorData;

// Key type definitions
typedef struct {
    const char* key;
    ControlType type;
} KeyTypeDef;

static const KeyTypeDef KEY_TYPES[] = {
    // [Game] section
    {"executable", CTRL_PATH_FILE}, {"directory", CTRL_PATH_FOLDER},
    {"isopath", CTRL_PATH_FILE}, {"gameexecutablepath", CTRL_PATH_FILE},
    {"profiledirectory", CTRL_PATH_FOLDER}, {"name", CTRL_TEXT},
    {"steamid", CTRL_TEXT},
    
    // [Launcher] section
    {"launcherexecutable", CTRL_PATH_FILE}, {"launchershortcut", CTRL_PATH_FILE},
    {"runasadmin", CTRL_BOOL}, {"hidetaskbar", CTRL_BOOL},
    {"borderless", CTRL_TEXT}, {"usekilllist", CTRL_BOOL},
    {"terminateborderlessonexit", CTRL_BOOL}, {"killlist", CTRL_LIST},
    
    // [Profiles] section
    {"player1profile", CTRL_PATH_FILE}, {"player2profile", CTRL_PATH_FILE},
    {"mediacenterprofile", CTRL_PATH_FILE}, {"multimonitorgamingconfig", CTRL_PATH_FILE},
    {"multimonitormediacenterconfig", CTRL_PATH_FILE},
    
    // Application sections - all follow same pattern: path, pathoptions, patharguments, pathrunwait
    {"controllermapperpath", CTRL_PATH_FILE}, {"controllermapperpathoptions", CTRL_TEXT},
    {"controllermapperpatharguments", CTRL_TEXT}, {"controllermapperrunwait", CTRL_BOOL},
    {"enablecontrollermapper", CTRL_BOOL},
    
    {"borderlesswindowingpath", CTRL_PATH_FILE}, {"borderlesswindowingpathoptions", CTRL_TEXT},
    {"borderlesswindowingpatharguments", CTRL_TEXT}, {"borderlesswindowingpathrunwait", CTRL_BOOL},
    {"enableborderlesswindowing", CTRL_BOOL},
    
    {"multimonitorpath", CTRL_PATH_FILE}, {"multimonitorpathoptions", CTRL_TEXT},
    {"multimonitorpatharguments", CTRL_TEXT}, {"multimonitorpathrunwait", CTRL_BOOL},
    {"enablemultimonitor", CTRL_BOOL},
    
    {"discmountpath", CTRL_PATH_FILE}, {"discmountpathoptions", CTRL_TEXT},
    {"discmountpatharguments", CTRL_TEXT}, {"discmountpathrunwait", CTRL_BOOL},
    {"enablediscmount", CTRL_BOOL},
    
    {"discunmountpath", CTRL_PATH_FILE}, {"discunmountpathoptions", CTRL_TEXT},
    {"discunmountpatharguments", CTRL_TEXT}, {"discunmountpathrunwait", CTRL_BOOL},
    {"enablediscunmount", CTRL_BOOL},
    
    {"cloudsyncpath", CTRL_PATH_FILE}, {"cloudsyncpathoptions", CTRL_TEXT},
    {"cloudsyncpatharguments", CTRL_TEXT}, {"cloudsyncpathrunwait", CTRL_BOOL},
    {"enablecloudsync", CTRL_BOOL},
    
    {"localbackuppath", CTRL_PATH_FILE}, {"localbackuppathoptions", CTRL_TEXT},
    {"localbackuppatharguments", CTRL_TEXT}, {"localbackuppathrunwait", CTRL_BOOL},
    {"enablelocalbackup", CTRL_BOOL},
    
    // Pre1, Pre2, Pre3 sections
    {"pre1path", CTRL_PATH_FILE}, {"pre1pathoptions", CTRL_TEXT},
    {"pre1patharguments", CTRL_TEXT}, {"pre1pathrunwait", CTRL_BOOL},
    {"enablepre1", CTRL_BOOL},
    
    {"pre2path", CTRL_PATH_FILE}, {"pre2pathoptions", CTRL_TEXT},
    {"pre2patharguments", CTRL_TEXT}, {"pre2pathrunwait", CTRL_BOOL},
    {"enablepre2", CTRL_BOOL},
    
    {"pre3path", CTRL_PATH_FILE}, {"pre3pathoptions", CTRL_TEXT},
    {"pre3patharguments", CTRL_TEXT}, {"pre3pathrunwait", CTRL_BOOL},
    {"enablepre3", CTRL_BOOL},
    
    // Post1, Post2, Post3 sections
    {"post1path", CTRL_PATH_FILE}, {"post1pathoptions", CTRL_TEXT},
    {"post1patharguments", CTRL_TEXT}, {"post1pathrunwait", CTRL_BOOL},
    {"enablepost1", CTRL_BOOL},
    
    {"post2path", CTRL_PATH_FILE}, {"post2pathoptions", CTRL_TEXT},
    {"post2patharguments", CTRL_TEXT}, {"post2pathrunwait", CTRL_BOOL},
    {"enablepost2", CTRL_BOOL},
    
    {"post3path", CTRL_PATH_FILE}, {"post3pathoptions", CTRL_TEXT},
    {"post3patharguments", CTRL_TEXT}, {"post3pathrunwait", CTRL_BOOL},
    {"enablepost3", CTRL_BOOL},
    
    // JustAfterLaunch and JustBeforeExit sections
    {"path", CTRL_PATH_FILE}, {"pathoptions", CTRL_TEXT},
    {"patharguments", CTRL_TEXT}, {"pathrunwait", CTRL_BOOL},
    {"enable", CTRL_BOOL},
    
    // [Sequences] section
    {"launchsequence", CTRL_LIST}, {"exitsequence", CTRL_LIST},
    
    // [SourceProfiles] and [SourceApplications] sections
    {"multimonitortool", CTRL_PATH_FILE}, {"antimicrox", CTRL_PATH_FILE},
    {"rclone", CTRL_PATH_FILE}, {"wincdemu", CTRL_PATH_FILE},
    {"osf", CTRL_PATH_FILE}, {"imgdrive", CTRL_PATH_FILE},
    {"cdmage", CTRL_PATH_FILE}, {"ludusavi", CTRL_PATH_FILE},
    {"gamesavemanager", CTRL_PATH_FILE}, {"gamebackupmonitor", CTRL_PATH_FILE},
    
    {NULL, CTRL_TEXT}
};

// Key abbreviations
typedef struct {
    const char* key;
    const char* abbrev;
} KeyAbbrev;

static const KeyAbbrev KEY_ABBREVS[] = {
    // [Game] section
    {"gameexecutablepath", "Game Exe"}, {"executable", "Executable"},
    {"directory", "Directory"}, {"name", "Name"}, {"isopath", "ISO Path"},
    {"steamid", "Steam ID"}, {"profiledirectory", "Profile Dir"},
    
    // [Launcher] section
    {"launchershortcut", "Shortcut"}, {"launcherexecutable", "Launcher Exe"},
    {"runasadmin", "Run Admin"}, {"hidetaskbar", "Hide Taskbar"},
    {"borderless", "Borderless"}, {"usekilllist", "Use Kill List"},
    {"terminateborderlessonexit", "Kill Border"}, {"killlist", "Kill List"},
    
    // [Profiles] section
    {"player1profile", "P1 Profile"}, {"player2profile", "P2 Profile"},
    {"mediacenterprofile", "MC Profile"}, {"multimonitorgamingconfig", "MM Game"},
    {"multimonitormediacenterconfig", "MM Desktop"},
    
    // [ControllerMapper] section
    {"enablecontrollermapper", "Enable Ctrl"}, {"controllermapperpath", "Ctrl Path"},
    {"controllermapperpathoptions", "Ctrl Opts"}, {"controllermapperpatharguments", "Ctrl Args"},
    {"controllermapperrunwait", "Ctrl Wait"},
    
    // [BorderlessWindowing] section
    {"enableborderlesswindowing", "Enable Border"}, {"borderlesswindowingpath", "Border Path"},
    {"borderlesswindowingpathoptions", "Border Opts"}, {"borderlesswindowingpatharguments", "Border Args"},
    {"borderlesswindowingpathrunwait", "Border Wait"},
    
    // [MultiMonitor] section
    {"enablemultimonitor", "Enable MM"}, {"multimonitorpath", "MM Path"},
    {"multimonitorpathoptions", "MM Opts"}, {"multimonitorpatharguments", "MM Args"},
    {"multimonitorpathrunwait", "MM Wait"},
    
    // [DiscMount] section
    {"enablediscmount", "Enable Mount"}, {"discmountpath", "Mount Path"},
    {"discmountpathoptions", "Mount Opts"}, {"discmountpatharguments", "Mount Args"},
    {"discmountpathrunwait", "Mount Wait"},
    
    // [DiscUnmount] section
    {"enablediscunmount", "Enable Unmount"}, {"discunmountpath", "Unmount Path"},
    {"discunmountpathoptions", "Unmount Opts"}, {"discunmountpatharguments", "Unmount Args"},
    {"discunmountpathrunwait", "Unmount Wait"},
    
    // [CloudSync] section
    {"enablecloudsync", "Enable Cloud"}, {"cloudsyncpath", "Cloud Path"},
    {"cloudsyncpathoptions", "Cloud Opts"}, {"cloudsyncpatharguments", "Cloud Args"},
    {"cloudsyncpathrunwait", "Cloud Wait"},
    
    // [LocalBackup] section
    {"enablelocalbackup", "Enable Backup"}, {"localbackuppath", "Backup Path"},
    {"localbackuppathoptions", "Backup Opts"}, {"localbackuppatharguments", "Backup Args"},
    {"localbackuppathrunwait", "Backup Wait"},
    
    // [Pre1/2/3] sections
    {"enablepre1", "Enable Pre1"}, {"pre1path", "Pre1 Path"},
    {"pre1pathoptions", "Pre1 Opts"}, {"pre1patharguments", "Pre1 Args"},
    {"pre1pathrunwait", "Pre1 Wait"},
    {"enablepre2", "Enable Pre2"}, {"pre2path", "Pre2 Path"},
    {"pre2pathoptions", "Pre2 Opts"}, {"pre2patharguments", "Pre2 Args"},
    {"pre2pathrunwait", "Pre2 Wait"},
    {"enablepre3", "Enable Pre3"}, {"pre3path", "Pre3 Path"},
    {"pre3pathoptions", "Pre3 Opts"}, {"pre3patharguments", "Pre3 Args"},
    {"pre3pathrunwait", "Pre3 Wait"},
    
    // [Post1/2/3] sections
    {"enablepost1", "Enable Post1"}, {"post1path", "Post1 Path"},
    {"post1pathoptions", "Post1 Opts"}, {"post1patharguments", "Post1 Args"},
    {"post1pathrunwait", "Post1 Wait"},
    {"enablepost2", "Enable Post2"}, {"post2path", "Post2 Path"},
    {"post2pathoptions", "Post2 Opts"}, {"post2patharguments", "Post2 Args"},
    {"post2pathrunwait", "Post2 Wait"},
    {"enablepost3", "Enable Post3"}, {"post3path", "Post3 Path"},
    {"post3pathoptions", "Post3 Opts"}, {"post3patharguments", "Post3 Args"},
    {"post3pathrunwait", "Post3 Wait"},
    
    // [JustAfterLaunch] and [JustBeforeExit] sections
    {"enable", "Enable"}, {"path", "Path"},
    {"pathoptions", "Options"}, {"patharguments", "Arguments"},
    {"pathrunwait", "Run Wait"},
    
    // [Sequences] section
    {"launchsequence", "Launch Seq"}, {"exitsequence", "Exit Seq"},
    
    // [SourceApplications] section
    {"multimonitortool", "MultiMon"}, {"antimicrox", "AntiMicroX"},
    {"rclone", "RClone"}, {"wincdemu", "WinCDEmu"},
    {"osf", "OSF"}, {"imgdrive", "ImgDrive"},
    {"cdmage", "CDMage"}, {"ludusavi", "Ludusavi"},
    {"gamesavemanager", "GameSaveMgr"}, {"gamebackupmonitor", "GameBackupMon"},
    
    {NULL, NULL}
};

// Forward declarations
LRESULT CALLBACK content_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp);
static int config_ini_handler(void* user, const char* sec, const char* name, const char* val);
void create_control(ConfigEditorData* data, const char* sec, const char* key, const char* val);
void save_config(ConfigEditorData* data);
ControlType get_type(const char* key);
const char* get_abbrev(const char* key);
void browse_path(HWND parent, HWND edit, BOOL folder);
void add_list_item(ConfigEditorData* data, int idx);
void remove_list_item(ConfigEditorData* data, int idx);
int CALLBACK browse_cb(HWND hwnd, UINT msg, LPARAM lp, LPARAM data);

// Phase 1: New button handlers
void import_config(ConfigEditorData* data);
void reset_config(ConfigEditorData* data);
void reload_apps(ConfigEditorData* data);
void export_config(ConfigEditorData* data);
void clear_controls(ConfigEditorData* data);
void reload_ini_file(ConfigEditorData* data, const char* ini_path);

static BOOL g_class_registered = FALSE;
static const char* CONTENT_CLASS = "ConfigEditorContent";

/**
 * Show config editor dialog
 */
BOOL show_config_editor(HWND parent, const char* ini_path) {
    ConfigEditorData* data = (ConfigEditorData*)calloc(1, sizeof(ConfigEditorData));
    if (!data) return FALSE;
    
    strncpy(data->ini_path, ini_path, MAX_PATH_LEN - 1);
    
    // Register content window class
    if (!g_class_registered) {
        WNDCLASSEXA wc = {0};
        wc.cbSize = sizeof(WNDCLASSEXA);
        wc.lpfnWndProc = content_proc;
        wc.hInstance = GetModuleHandle(NULL);
        wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
        wc.lpszClassName = CONTENT_CLASS;
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        
        if (RegisterClassExA(&wc)) {
            g_class_registered = TRUE;
        }
    }
    
    // Register dialog class
    static BOOL dialog_class_registered = FALSE;
    if (!dialog_class_registered) {
        WNDCLASSEXA wc = {0};
        wc.cbSize = sizeof(WNDCLASSEXA);
        wc.lpfnWndProc = DefDlgProcA;
        wc.hInstance = GetModuleHandle(NULL);
        wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
        wc.lpszClassName = "ConfigEditorDialog";
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.cbWndExtra = DLGWINDOWEXTRA;
        
        if (RegisterClassExA(&wc)) {
            dialog_class_registered = TRUE;
        }
    }
    
    // Create dialog window manually
    int x = (GetSystemMetrics(SM_CXSCREEN) - DIALOG_WIDTH) / 2;
    int y = (GetSystemMetrics(SM_CYSCREEN) - DIALOG_HEIGHT) / 2;
    
    HWND hwnd = CreateWindowExA(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST | WS_EX_WINDOWEDGE,
        "ConfigEditorDialog",
        "Edit Configuration",
        WS_POPUP | WS_CAPTION | WS_SYSMENU,
        x, y, DIALOG_WIDTH, DIALOG_HEIGHT,
        parent,
        NULL,
        GetModuleHandle(NULL),
        NULL
    );
    
    if (!hwnd) {
        log_message("ERROR", "Failed to create config editor dialog window");
        free(data);
        return FALSE;
    }
    
    log_message("INFO", "Config editor dialog window created successfully");
    
    // Initialize dialog
    data->dialog = hwnd;
    data->modified = FALSE;
    strncpy(data->original_ini_path, ini_path, MAX_PATH_LEN - 1);
    SetWindowLongPtrA(hwnd, GWLP_USERDATA, (LONG_PTR)data);
    
    // Create content area
    data->content_area = CreateWindowExA(
        WS_EX_CLIENTEDGE, CONTENT_CLASS, NULL,
        WS_CHILD | WS_VISIBLE | WS_VSCROLL,
        10, 10, DIALOG_WIDTH - 40, DIALOG_HEIGHT - 60,
        hwnd, NULL, GetModuleHandle(NULL), data
    );
    
    // Load INI
    data->control_count = 0;
    data->content_height = 10;
    ini_parse(data->ini_path, config_ini_handler, data);
    
    // Setup scrollbar
    SCROLLINFO si = {0};
    si.cbSize = sizeof(SCROLLINFO);
    si.fMask = SIF_RANGE | SIF_PAGE;
    si.nMin = 0;
    si.nMax = data->content_height;
    si.nPage = DIALOG_HEIGHT - 60;
    SetScrollInfo(data->content_area, SB_VERT, &si, TRUE);
    
    // Create 6 action buttons (left-aligned, compact)
    int btn_y = DIALOG_HEIGHT - 40;
    int btn_x = 10;
    int btn_spacing = 5;
    
    CreateWindowExA(0, "BUTTON", "Imprt",
        WS_CHILD | WS_VISIBLE,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_IMPORT_BTN, GetModuleHandle(NULL), NULL);
    btn_x += ACTION_BTN_WIDTH + btn_spacing;
    
    CreateWindowExA(0, "BUTTON", "Reset",
        WS_CHILD | WS_VISIBLE,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_RESET_BTN, GetModuleHandle(NULL), NULL);
    btn_x += ACTION_BTN_WIDTH + btn_spacing;
    
    CreateWindowExA(0, "BUTTON", "Reload",
        WS_CHILD | WS_VISIBLE,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_RELOAD_BTN, GetModuleHandle(NULL), NULL);
    btn_x += ACTION_BTN_WIDTH + btn_spacing;
    
    CreateWindowExA(0, "BUTTON", "Save",
        WS_CHILD | WS_VISIBLE,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_SAVE_BTN, GetModuleHandle(NULL), NULL);
    btn_x += ACTION_BTN_WIDTH + btn_spacing;
    
    CreateWindowExA(0, "BUTTON", "Exprt",
        WS_CHILD | WS_VISIBLE,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_EXPORT_BTN, GetModuleHandle(NULL), NULL);
    btn_x += ACTION_BTN_WIDTH + btn_spacing;
    
    CreateWindowExA(0, "BUTTON", "Ok",
        WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON,
        btn_x, btn_y, ACTION_BTN_WIDTH, ACTION_BTN_HEIGHT,
        hwnd, (HMENU)IDC_OK_BTN, GetModuleHandle(NULL), NULL);
    
    // Show and update window
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    SetForegroundWindow(hwnd);
    
    // Message loop
    MSG msg;
    BOOL result = FALSE;
    
    while (GetMessage(&msg, NULL, 0, 0)) {
        if (msg.message == WM_COMMAND && msg.hwnd == hwnd) {
            int id = LOWORD(msg.wParam);
            
            if (id == IDC_SAVE_BTN) {
                save_config(data);
                result = TRUE;
                break;
            } else if (id == IDC_CANCEL_BTN) {
                result = FALSE;
                break;
            }
        } else if (msg.message == WM_CLOSE && msg.hwnd == hwnd) {
            result = FALSE;
            break;
        }
        
        if (!IsDialogMessage(hwnd, &msg)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
    }
    
    DestroyWindow(hwnd);
    free(data);
    return result;
}

/**
 * Content window procedure
 */
LRESULT CALLBACK content_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    ConfigEditorData* data = (ConfigEditorData*)GetWindowLongPtrA(hwnd, GWLP_USERDATA);
    
    switch (msg) {
        case WM_CREATE: {
            CREATESTRUCTA* cs = (CREATESTRUCTA*)lp;
            SetWindowLongPtrA(hwnd, GWLP_USERDATA, (LONG_PTR)cs->lpCreateParams);
            return 0;
        }
        
        case WM_COMMAND: {
            if (!data) break;
            
            int id = LOWORD(wp);
            int notify = HIWORD(wp);
            
            if (id >= IDC_CONTROL_BASE) {
                int ctrl_idx = (id - IDC_CONTROL_BASE) / 10;
                int action = (id - IDC_CONTROL_BASE) % 10;
                
                if (ctrl_idx < data->control_count) {
                    ConfigControl* ctrl = &data->controls[ctrl_idx];
                    
                    if (action == 1 && notify == BN_CLICKED) {
                        // Browse button
                        browse_path(GetParent(hwnd), ctrl->edit, 
                                  ctrl->type == CTRL_PATH_FOLDER);
                    } else if (action == 2 && notify == BN_CLICKED) {
                        // Add button
                        add_list_item(data, ctrl_idx);
                    } else if (action == 3 && notify == BN_CLICKED) {
                        // Remove button
                        remove_list_item(data, ctrl_idx);
                    }
                }
            }
            break;
        }
        
        case WM_VSCROLL: {
            if (!data) break;
            
            SCROLLINFO si = {0};
            si.cbSize = sizeof(SCROLLINFO);
            si.fMask = SIF_ALL;
            GetScrollInfo(hwnd, SB_VERT, &si);
            
            int old_pos = si.nPos;
            
            switch (LOWORD(wp)) {
                case SB_LINEUP: si.nPos -= 20; break;
                case SB_LINEDOWN: si.nPos += 20; break;
                case SB_PAGEUP: si.nPos -= si.nPage; break;
                case SB_PAGEDOWN: si.nPos += si.nPage; break;
                case SB_THUMBTRACK: si.nPos = si.nTrackPos; break;
            }
            
            si.fMask = SIF_POS;
            SetScrollInfo(hwnd, SB_VERT, &si, TRUE);
            GetScrollInfo(hwnd, SB_VERT, &si);
            
            if (si.nPos != old_pos) {
                int dy = old_pos - si.nPos;
                ScrollWindow(hwnd, 0, dy, NULL, NULL);
                UpdateWindow(hwnd);
                data->scroll_pos = si.nPos;
            }
            return 0;
        }
        
        case WM_MOUSEWHEEL: {
            if (!data) break;
            int delta = GET_WHEEL_DELTA_WPARAM(wp);
            SendMessage(hwnd, WM_VSCROLL, delta > 0 ? SB_LINEUP : SB_LINEDOWN, 0);
            return 0;
        }
        
        case WM_CTLCOLORSTATIC:
        case WM_CTLCOLOREDIT:
            return (LRESULT)GetStockObject(WHITE_BRUSH);
    }
    return DefWindowProcA(hwnd, msg, wp, lp);
}

/**
 * INI parser callback
 */
static int config_ini_handler(void* user, const char* sec, const char* name, const char* val) {
    ConfigEditorData* data = (ConfigEditorData*)user;
    create_control(data, sec, name, val);
    return 1;
}

/**
 * Create control for key
 */
void create_control(ConfigEditorData* data, const char* sec, const char* key, const char* val) {
    if (data->control_count >= MAX_CONTROLS) return;
    
    ConfigControl* ctrl = &data->controls[data->control_count];
    strncpy(ctrl->section, sec, sizeof(ctrl->section) - 1);
    strncpy(ctrl->key, key, sizeof(ctrl->key) - 1);
    strncpy(ctrl->value, val ? val : "", sizeof(ctrl->value) - 1);
    ctrl->type = get_type(key);
    ctrl->y_pos = data->content_height - data->scroll_pos;
    ctrl->id = IDC_CONTROL_BASE + (data->control_count * 10);
    
    int x_label = 5;
    int x_edit = x_label + LABEL_WIDTH + 5;
    int y = ctrl->y_pos;
    
    // Label
    const char* label_text = get_abbrev(key);
    ctrl->label = CreateWindowExA(0, "STATIC", label_text,
        WS_CHILD | WS_VISIBLE | SS_RIGHT,
        x_label, y + 3, LABEL_WIDTH, 18,
        data->content_area, NULL, GetModuleHandle(NULL), NULL);
    
    // Create widget based on type
    switch (ctrl->type) {
        case CTRL_BOOL: {
            ctrl->button = CreateWindowExA(0, "BUTTON", "",
                WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX,
                x_edit, y, 20, 20,
                data->content_area, (HMENU)(ctrl->id),
                GetModuleHandle(NULL), NULL);
            
            if (_stricmp(val, "true") == 0 || _stricmp(val, "1") == 0) {
                SendMessage(ctrl->button, BM_SETCHECK, BST_CHECKED, 0);
            }
            break;
        }
        
        case CTRL_LIST: {
            ctrl->combo = CreateWindowExA(WS_EX_CLIENTEDGE, "COMBOBOX", "",
                WS_CHILD | WS_VISIBLE | CBS_DROPDOWN | WS_VSCROLL,
                x_edit, y, EDIT_WIDTH - 70, 200,
                data->content_area, (HMENU)(ctrl->id),
                GetModuleHandle(NULL), NULL);
            
            // Parse and add items
            if (val && strlen(val) > 0) {
                char* copy = _strdup(val);
                char* ctx = NULL;
                char* tok = strtok_s(copy, ",", &ctx);
                while (tok) {
                    while (*tok == ' ') tok++;
                    char* end = tok + strlen(tok) - 1;
                    while (end > tok && *end == ' ') *end-- = '\0';
                    
                    if (*tok) {
                        SendMessageA(ctrl->combo, CB_ADDSTRING, 0, (LPARAM)tok);
                    }
                    tok = strtok_s(NULL, ",", &ctx);
                }
                free(copy);
                
                if (SendMessage(ctrl->combo, CB_GETCOUNT, 0, 0) > 0) {
                    SendMessage(ctrl->combo, CB_SETCURSEL, 0, 0);
                }
            }
            
            // Add/Remove buttons
            ctrl->add_btn = CreateWindowExA(0, "BUTTON", "+",
                WS_CHILD | WS_VISIBLE,
                x_edit + EDIT_WIDTH - 65, y, 30, 20,
                data->content_area, (HMENU)(ctrl->id + 2),
                GetModuleHandle(NULL), NULL);
            
            ctrl->del_btn = CreateWindowExA(0, "BUTTON", "-",
                WS_CHILD | WS_VISIBLE,
                x_edit + EDIT_WIDTH - 30, y, 30, 20,
                data->content_area, (HMENU)(ctrl->id + 3),
                GetModuleHandle(NULL), NULL);
            break;
        }
        
        case CTRL_PATH_FILE:
        case CTRL_PATH_FOLDER: {
            ctrl->edit = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", val,
                WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
                x_edit, y, EDIT_WIDTH - 35, 20,
                data->content_area, (HMENU)(ctrl->id),
                GetModuleHandle(NULL), NULL);
            
            ctrl->button = CreateWindowExA(0, "BUTTON", "...",
                WS_CHILD | WS_VISIBLE,
                x_edit + EDIT_WIDTH - 30, y, 30, 20,
                data->content_area, (HMENU)(ctrl->id + 1),
                GetModuleHandle(NULL), NULL);
            break;
        }
        
        default: { // CTRL_TEXT
            ctrl->edit = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", val,
                WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
                x_edit, y, EDIT_WIDTH, 20,
                data->content_area, (HMENU)(ctrl->id),
                GetModuleHandle(NULL), NULL);
            break;
        }
    }
    
    data->content_height += CONTROL_HEIGHT;
    data->control_count++;
}

/**
 * Save configuration
 */
void save_config(ConfigEditorData* data) {
    FILE* f = fopen(data->ini_path, "w");
    if (!f) return;
    
    // Group by section
    const char* current_section = "";
    
    for (int i = 0; i < data->control_count; i++) {
        ConfigControl* ctrl = &data->controls[i];
        
        // Write section header if changed
        if (strcmp(current_section, ctrl->section) != 0) {
            fprintf(f, "\n[%s]\n", ctrl->section);
            current_section = ctrl->section;
        }
        
        // Get value from control
        char value[MAX_CMD_LEN] = "";
        
        switch (ctrl->type) {
            case CTRL_BOOL: {
                LRESULT checked = SendMessage(ctrl->button, BM_GETCHECK, 0, 0);
                strcpy(value, (checked == BST_CHECKED) ? "True" : "False");
                break;
            }
            
            case CTRL_LIST: {
                int count = SendMessage(ctrl->combo, CB_GETCOUNT, 0, 0);
                value[0] = '\0';
                for (int j = 0; j < count; j++) {
                    char item[256];
                    SendMessageA(ctrl->combo, CB_GETLBTEXT, j, (LPARAM)item);
                    if (j > 0) strcat(value, ",");
                    strcat(value, item);
                }
                break;
            }
            
            default: { // TEXT, PATH_FILE, PATH_FOLDER
                if (ctrl->edit) {
                    GetWindowTextA(ctrl->edit, value, sizeof(value));
                }
                break;
            }
        }
        
        // Write key=value
        fprintf(f, "%s = %s\n", ctrl->key, value);
    }
    
    fclose(f);
}

/**
 * Get control type for key
 */
ControlType get_type(const char* key) {
    char key_lower[64];
    strncpy(key_lower, key, sizeof(key_lower) - 1);
    _strlwr(key_lower);
    
    for (int i = 0; KEY_TYPES[i].key != NULL; i++) {
        if (strcmp(key_lower, KEY_TYPES[i].key) == 0) {
            return KEY_TYPES[i].type;
        }
    }
    
    // Infer from name
    if (strstr(key_lower, "path") || strstr(key_lower, "app") || 
        strstr(key_lower, "profile") || strstr(key_lower, "executable")) {
        return CTRL_PATH_FILE;
    } else if (strstr(key_lower, "directory") || strstr(key_lower, "folder")) {
        return CTRL_PATH_FOLDER;
    } else if (strstr(key_lower, "wait") || strstr(key_lower, "enable") || 
               strstr(key_lower, "use") || strstr(key_lower, "hide")) {
        return CTRL_BOOL;
    }
    
    return CTRL_TEXT;
}

/**
 * Get abbreviated label
 */
const char* get_abbrev(const char* key) {
    char key_lower[64];
    strncpy(key_lower, key, sizeof(key_lower) - 1);
    _strlwr(key_lower);
    
    for (int i = 0; KEY_ABBREVS[i].key != NULL; i++) {
        if (strcmp(key_lower, KEY_ABBREVS[i].key) == 0) {
            return KEY_ABBREVS[i].abbrev;
        }
    }
    
    return key;
}

/**
 * Browse for file or folder
 */
void browse_path(HWND parent, HWND edit, BOOL folder) {
    char path[MAX_PATH_LEN] = "";
    GetWindowTextA(edit, path, MAX_PATH_LEN);
    
    if (folder) {
        // Folder browser
        BROWSEINFOA bi = {0};
        bi.hwndOwner = parent;
        bi.lpszTitle = "Select Folder";
        bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
        bi.lpfn = browse_cb;
        bi.lParam = (LPARAM)path;
        
        LPITEMIDLIST pidl = SHBrowseForFolderA(&bi);
        if (pidl) {
            if (SHGetPathFromIDListA(pidl, path)) {
                // Convert to forward slashes
                for (char* p = path; *p; p++) {
                    if (*p == '\\') *p = '/';
                }
                SetWindowTextA(edit, path);
            }
            CoTaskMemFree(pidl);
        }
    } else {
        // File browser
        OPENFILENAMEA ofn = {0};
        ofn.lStructSize = sizeof(ofn);
        ofn.hwndOwner = parent;
        ofn.lpstrFile = path;
        ofn.nMaxFile = MAX_PATH_LEN;
        ofn.lpstrFilter = "All Files\0*.*\0Executables\0*.exe\0";
        ofn.nFilterIndex = 1;
        ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST;
        
        if (GetOpenFileNameA(&ofn)) {
            // Convert to forward slashes
            for (char* p = path; *p; p++) {
                if (*p == '\\') *p = '/';
            }
            SetWindowTextA(edit, path);
        }
    }
}

/**
 * Browse callback for folder selection
 */
int CALLBACK browse_cb(HWND hwnd, UINT msg, LPARAM lp, LPARAM data) {
    (void)lp; // Unused
    if (msg == BFFM_INITIALIZED && data) {
        SendMessageA(hwnd, BFFM_SETSELECTION, TRUE, data);
    }
    return 0;
}

/**
 * Add item to list
 */
void add_list_item(ConfigEditorData* data, int idx) {
    if (idx >= data->control_count) return;
    
    ConfigControl* ctrl = &data->controls[idx];
    if (ctrl->type != CTRL_LIST || !ctrl->combo) return;
    
    int cur_idx = SendMessage(ctrl->combo, CB_GETCURSEL, 0, 0);
    
    // Insert empty item at current position
    SendMessageA(ctrl->combo, CB_INSERTSTRING, cur_idx, (LPARAM)"");
    SendMessage(ctrl->combo, CB_SETCURSEL, cur_idx, 0);
    
    // Focus the combo box for editing
    SetFocus(ctrl->combo);
}

/**
 * Remove item from list
 */
void remove_list_item(ConfigEditorData* data, int idx) {
    if (idx >= data->control_count) return;
    
    ConfigControl* ctrl = &data->controls[idx];
    if (ctrl->type != CTRL_LIST || !ctrl->combo) return;
    
    int cur_idx = SendMessage(ctrl->combo, CB_GETCURSEL, 0, 0);
    if (cur_idx >= 0) {
        SendMessage(ctrl->combo, CB_DELETESTRING, cur_idx, 0);
        
        // Select next item or previous if at end
        int count = SendMessage(ctrl->combo, CB_GETCOUNT, 0, 0);
        if (count > 0) {
            if (cur_idx >= count) cur_idx = count - 1;
            SendMessage(ctrl->combo, CB_SETCURSEL, cur_idx, 0);
        }
    }
}
