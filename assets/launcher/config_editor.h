/**
 * config_editor.h - Advanced Configuration Editor Header
 *
 * Full GUI implementation with parity to Python version.
 * Features smart widgets for paths, booleans, lists, and text fields.
 */

#ifndef CONFIG_EDITOR_H
#define CONFIG_EDITOR_H

#include <windows.h>

/**
 * Show advanced configuration editor dialog
 * 
 * Creates a scrollable modal window with smart widgets:
 * - Path fields with browse buttons
 * - Checkboxes for boolean values
 * - Comboboxes with +/- buttons for lists
 * - Text fields for other values
 * 
 * @param parent Parent window handle (can be NULL)
 * @param ini_path Path to Game.ini file
 * @return TRUE if configuration was saved, FALSE if cancelled
 */
BOOL show_config_editor(HWND parent, const char* ini_path);

#endif // CONFIG_EDITOR_H
