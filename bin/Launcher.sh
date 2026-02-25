#!/usr/bin/env bash
# Launcher.sh - Game Launcher Bash Script
# A Linux/macOS bash script port of the Launcher functionality

set -e  # Exit on error

# ===== INITIALIZATION =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME="$(dirname "$SCRIPT_DIR")"
LOGFILE="$HOME/launcher.log"
PLINK="$1"

# Initialize log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launcher started. Home directory: $HOME" > "$LOGFILE"

# Check if target was provided
if [ -z "$PLINK" ]; then
    echo "No target specified. Usage: Launcher.sh <target>"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: No target specified" >> "$LOGFILE"
    sleep 3
    exit 1
fi

echo "Launching: $PLINK"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching: $PLINK" >> "$LOGFILE"

# ===== PARSE TARGET =====
SCPATH="$(dirname "$PLINK")"
GAMENAME="$(basename "$PLINK" | sed 's/\.[^.]*$//')"

# ===== LOAD CONFIGURATION =====
GAMEINI="$SCPATH/Game.ini"
if [ ! -f "$GAMEINI" ]; then
    GAMEINI="$HOME/config.ini"
fi

if [ ! -f "$GAMEINI" ]; then
    echo "Configuration file not found"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Configuration file not found" >> "$LOGFILE"
    sleep 3
    exit 1
fi

echo "Loading configuration from: $GAMEINI"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Loading configuration from: $GAMEINI" >> "$LOGFILE"

# ===== HELPER FUNCTION: Read INI =====
read_ini() {
    local file="$1" section="$2" key="$3" in_section=0 value=""
    while IFS='=' read -r line_key line_value; do
        line_key=$(echo "$line_key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        line_value=$(echo "$line_value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [[ "$line_key" =~ ^\[.*\]$ ]]; then
            section_name="${line_key#[}"; section_name="${section_name%]}"
            [ "$section_name" = "$section" ] && in_section=1 || in_section=0
        elif [ $in_section -eq 1 ] && [ "$line_key" = "$key" ]; then
            value="$line_value"; break
        fi
    done < "$file"
    echo "$value"
}

# ===== PARSE INI FILE =====
GAMEPATH=$(read_ini "$GAMEINI" "Game" "Executable")
GAMEDIR=$(read_ini "$GAMEINI" "Game" "Directory")
GAMENAME_INI=$(read_ini "$GAMEINI" "Game" "Name")
ISOPATH=$(read_ini "$GAMEINI" "Game" "IsoPath")
RUNASADMIN=$(read_ini "$GAMEINI" "Options" "RunAsAdmin")
USEKILLLIST=$(read_ini "$GAMEINI" "Options" "UseKillList")
KILLLIST=$(read_ini "$GAMEINI" "Options" "KillList")
MAPPERAPP=$(read_ini "$GAMEINI" "Paths" "ControllerMapperApp")
MAPPEROPTS=$(read_ini "$GAMEINI" "Paths" "ControllerMapperOptions")
MAPPERARGS=$(read_ini "$GAMEINI" "Paths" "ControllerMapperArguments")
BORDERLESSAPP=$(read_ini "$GAMEINI" "Paths" "BorderlessWindowingApp")
BORDERLESSOPTS=$(read_ini "$GAMEINI" "Paths" "BorderlessWindowingOptions")
BORDERLESSARGS=$(read_ini "$GAMEINI" "Paths" "BorderlessWindowingArguments")
MMTOOL=$(read_ini "$GAMEINI" "Paths" "MultiMonitorTool")
MMOPTS=$(read_ini "$GAMEINI" "Paths" "MultiMonitorOptions")
MMGAMECONFIG=$(read_ini "$GAMEINI" "Paths" "MultiMonitorGamingConfig")
MMDESKTOPCONFIG=$(read_ini "$GAMEINI" "Paths" "MultiMonitorDesktopConfig")
MOUNTAPP=$(read_ini "$GAMEINI" "Paths" "DiscMountApp")
MOUNTOPTS=$(read_ini "$GAMEINI" "Paths" "DiscMountOptions")
MOUNTARGS=$(read_ini "$GAMEINI" "Paths" "DiscMountArguments")
UNMOUNTAPP=$(read_ini "$GAMEINI" "Paths" "DiscUnmountApp")
UNMOUNTOPTS=$(read_ini "$GAMEINI" "Paths" "DiscUnmountOptions")
UNMOUNTARGS=$(read_ini "$GAMEINI" "Paths" "DiscUnmountArguments")
PREAPP1=$(read_ini "$GAMEINI" "PreLaunch" "App1")
PREAPP1OPTS=$(read_ini "$GAMEINI" "PreLaunch" "App1Options")
PREAPP1ARGS=$(read_ini "$GAMEINI" "PreLaunch" "App1Arguments")
PREAPP1WAIT=$(read_ini "$GAMEINI" "PreLaunch" "App1Wait")
PREAPP2=$(read_ini "$GAMEINI" "PreLaunch" "App2")
PREAPP2OPTS=$(read_ini "$GAMEINI" "PreLaunch" "App2Options")
PREAPP2ARGS=$(read_ini "$GAMEINI" "PreLaunch" "App2Arguments")
PREAPP2WAIT=$(read_ini "$GAMEINI" "PreLaunch" "App2Wait")
PREAPP3=$(read_ini "$GAMEINI" "PreLaunch" "App3")
PREAPP3OPTS=$(read_ini "$GAMEINI" "PreLaunch" "App3Options")
PREAPP3ARGS=$(read_ini "$GAMEINI" "PreLaunch" "App3Arguments")
PREAPP3WAIT=$(read_ini "$GAMEINI" "PreLaunch" "App3Wait")
POSTAPP1=$(read_ini "$GAMEINI" "PostLaunch" "App1")
POSTAPP1OPTS=$(read_ini "$GAMEINI" "PostLaunch" "App1Options")
POSTAPP1ARGS=$(read_ini "$GAMEINI" "PostLaunch" "App1Arguments")
POSTAPP1WAIT=$(read_ini "$GAMEINI" "PostLaunch" "App1Wait")
POSTAPP2=$(read_ini "$GAMEINI" "PostLaunch" "App2")
POSTAPP2OPTS=$(read_ini "$GAMEINI" "PostLaunch" "App2Options")
POSTAPP2ARGS=$(read_ini "$GAMEINI" "PostLaunch" "App2Arguments")
POSTAPP2WAIT=$(read_ini "$GAMEINI" "PostLaunch" "App2Wait")
POSTAPP3=$(read_ini "$GAMEINI" "PostLaunch" "App3")
POSTAPP3OPTS=$(read_ini "$GAMEINI" "PostLaunch" "App3Options")
POSTAPP3ARGS=$(read_ini "$GAMEINI" "PostLaunch" "App3Arguments")
POSTAPP3WAIT=$(read_ini "$GAMEINI" "PostLaunch" "App3Wait")
JUSTAFTERAPP=$(read_ini "$GAMEINI" "PostLaunch" "JustAfterLaunchApp")
JUSTAFTEROPTS=$(read_ini "$GAMEINI" "PostLaunch" "JustAfterLaunchOptions")
JUSTAFTERARGS=$(read_ini "$GAMEINI" "PostLaunch" "JustAfterLaunchArguments")
JUSTAFTERWAIT=$(read_ini "$GAMEINI" "PostLaunch" "JustAfterLaunchWait")
JUSTBEFOREAPP=$(read_ini "$GAMEINI" "PostLaunch" "JustBeforeExitApp")
JUSTBEFOREOPTS=$(read_ini "$GAMEINI" "PostLaunch" "JustBeforeExitOptions")
JUSTBEFOREARGS=$(read_ini "$GAMEINI" "PostLaunch" "JustBeforeExitArguments")
JUSTBEFOREWAIT=$(read_ini "$GAMEINI" "PostLaunch" "JustBeforeExitWait")
LAUNCHSEQ=$(read_ini "$GAMEINI" "Sequences" "LaunchSequence")
EXITSEQ=$(read_ini "$GAMEINI" "Sequences" "ExitSequence")

# CloudSync section
CLOUDENABLED=$(read_ini "$GAMEINI" "CloudSync" "Enabled")
CLOUDAPP=$(read_ini "$GAMEINI" "CloudSync" "App")
CLOUDOPTS=$(read_ini "$GAMEINI" "CloudSync" "Options")
CLOUDARGS=$(read_ini "$GAMEINI" "CloudSync" "Arguments")
CLOUDWAIT=$(read_ini "$GAMEINI" "CloudSync" "Wait")
CLOUDBACKUPONLAUNCH=$(read_ini "$GAMEINI" "CloudSync" "BackupOnLaunch")
CLOUDUPLOADONEXIT=$(read_ini "$GAMEINI" "CloudSync" "UploadOnExit")

# LocalBackup section
BACKUPENABLED=$(read_ini "$GAMEINI" "LocalBackup" "Enabled")
BACKUPAPP=$(read_ini "$GAMEINI" "LocalBackup" "App")
BACKUPOPTS=$(read_ini "$GAMEINI" "LocalBackup" "Options")
BACKUPARGS=$(read_ini "$GAMEINI" "LocalBackup" "Arguments")
BACKUPWAIT=$(read_ini "$GAMEINI" "LocalBackup" "Wait")
BACKUPBACKUPONLAUNCH=$(read_ini "$GAMEINI" "LocalBackup" "BackupOnLaunch")
BACKUPBACKUPONEXIT=$(read_ini "$GAMEINI" "LocalBackup" "BackupOnExit")

# Set defaults
[ -z "$LAUNCHSEQ" ] && LAUNCHSEQ="Cloud-Sync,Local-Backup,Controller-Mapper,Monitor-Config,mount-disc,Pre1,Pre2,Pre3,Borderless"
[ -z "$EXITSEQ" ] && EXITSEQ="Post1,Post2,Post3,Unmount-disc,Monitor-Config,Controller-Mapper,Local-Backup,Cloud-Sync"
[ -n "$GAMENAME_INI" ] && GAMENAME="$GAMENAME_INI"
[ -z "$GAMEPATH" ] && GAMEPATH="$PLINK"
[ -z "$GAMEDIR" ] && GAMEDIR="$(dirname "$GAMEPATH")"

echo "Game: $GAMENAME, Path: $GAMEPATH, Directory: $GAMEDIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Game: $GAMENAME, Path: $GAMEPATH, Dir: $GAMEDIR" >> "$LOGFILE"

# ===== HELPER FUNCTIONS =====
run_app() {
    local app_path="$1" app_opts="$2" app_args="$3" app_wait="$4"
    [ -z "$app_path" ] && return
    local full_cmd="$app_path"
    [ -n "$app_opts" ] && full_cmd="$full_cmd $app_opts"
    [ -n "$app_args" ] && full_cmd="$full_cmd $app_args"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]     Executing: $full_cmd" >> "$LOGFILE"
    if [[ "$app_wait" =~ ^[1Tt] ]]; then
        eval "$full_cmd" 2>>"$LOGFILE"
    else
        eval "$full_cmd" 2>>"$LOGFILE" &
    fi
}

execute_sequence_item() {
    local item="$1" phase="$2"
    echo "  Sequence: $item"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]   Sequence: $item" >> "$LOGFILE"
    case "$item" in
        "Controller-Mapper")
            if [ "$phase" = "launch" ]; then
                [ -n "$MAPPERAPP" ] && echo "    Starting Controller Mapper..." && run_app "$MAPPERAPP" "$MAPPEROPTS" "$MAPPERARGS" "0"
            else
                [ -n "$MAPPERAPP" ] && echo "    Stopping Controller Mapper..." && pkill -f "$(basename "$MAPPERAPP")" 2>/dev/null || true
            fi ;;
        "Monitor-Config")
            if [ "$phase" = "launch" ]; then
                [ -n "$MMTOOL" ] && [ -n "$MMGAMECONFIG" ] && echo "    Applying gaming monitor config..." && run_app "$MMTOOL" "$MMOPTS" "/LoadConfig \"$MMGAMECONFIG\"" "1"
            else
                [ -n "$MMTOOL" ] && [ -n "$MMDESKTOPCONFIG" ] && echo "    Restoring desktop monitor config..." && run_app "$MMTOOL" "$MMOPTS" "/LoadConfig \"$MMDESKTOPCONFIG\"" "1"
            fi ;;
        "mount-disc")
            [ -n "$MOUNTAPP" ] && [ -n "$ISOPATH" ] && echo "    Mounting disc: $ISOPATH..." && run_app "$MOUNTAPP" "$MOUNTOPTS" "\"$ISOPATH\" $MOUNTARGS" "1" ;;
        "Unmount-disc")
            [ -n "$UNMOUNTAPP" ] && [ -n "$ISOPATH" ] && echo "    Unmounting disc..." && run_app "$UNMOUNTAPP" "$UNMOUNTOPTS" "\"$ISOPATH\" $UNMOUNTARGS" "1" ;;
        "Borderless")
            [ -n "$BORDERLESSAPP" ] && echo "    Starting Borderless Gaming..." && run_app "$BORDERLESSAPP" "$BORDERLESSOPTS" "$BORDERLESSARGS" "0" ;;
        "Pre1")
            [ -n "$PREAPP1" ] && echo "    Running Pre-Launch App 1..." && run_app "$PREAPP1" "$PREAPP1OPTS" "$PREAPP1ARGS" "$PREAPP1WAIT" ;;
        "Pre2")
            [ -n "$PREAPP2" ] && echo "    Running Pre-Launch App 2..." && run_app "$PREAPP2" "$PREAPP2OPTS" "$PREAPP2ARGS" "$PREAPP2WAIT" ;;
        "Pre3")
            [ -n "$PREAPP3" ] && echo "    Running Pre-Launch App 3..." && run_app "$PREAPP3" "$PREAPP3OPTS" "$PREAPP3ARGS" "$PREAPP3WAIT" ;;
        "Post1")
            [ -n "$POSTAPP1" ] && echo "    Running Post-Launch App 1..." && run_app "$POSTAPP1" "$POSTAPP1OPTS" "$POSTAPP1ARGS" "$POSTAPP1WAIT" ;;
        "Post2")
            [ -n "$POSTAPP2" ] && echo "    Running Post-Launch App 2..." && run_app "$POSTAPP2" "$POSTAPP2OPTS" "$POSTAPP2ARGS" "$POSTAPP2WAIT" ;;
        "Post3")
            [ -n "$POSTAPP3" ] && echo "    Running Post-Launch App 3..." && run_app "$POSTAPP3" "$POSTAPP3OPTS" "$POSTAPP3ARGS" "$POSTAPP3WAIT" ;;
        "Cloud-Sync")
            if [[ "$CLOUDENABLED" =~ ^[1Tt] ]]; then
                if [ "$phase" = "launch" ]; then
                    if [[ "$CLOUDBACKUPONLAUNCH" =~ ^[1Tt] ]]; then
                        [ -n "$CLOUDAPP" ] && echo "    Running Cloud Sync (download)..." && run_app "$CLOUDAPP" "$CLOUDOPTS" "$CLOUDARGS" "$CLOUDWAIT"
                    fi
                else
                    if [[ "$CLOUDUPLOADONEXIT" =~ ^[1Tt] ]]; then
                        [ -n "$CLOUDAPP" ] && echo "    Running Cloud Sync (upload)..." && run_app "$CLOUDAPP" "$CLOUDOPTS" "$CLOUDARGS" "$CLOUDWAIT"
                    fi
                fi
            fi ;;
        "Local-Backup")
            if [[ "$BACKUPENABLED" =~ ^[1Tt] ]]; then
                if [ "$phase" = "launch" ]; then
                    if [[ "$BACKUPBACKUPONLAUNCH" =~ ^[1Tt] ]]; then
                        [ -n "$BACKUPAPP" ] && echo "    Running Local Backup (pre-launch)..." && run_app "$BACKUPAPP" "$BACKUPOPTS" "$BACKUPARGS" "$BACKUPWAIT"
                    fi
                else
                    if [[ "$BACKUPBACKUPONEXIT" =~ ^[1Tt] ]]; then
                        [ -n "$BACKUPAPP" ] && echo "    Running Local Backup (post-exit)..." && run_app "$BACKUPAPP" "$BACKUPOPTS" "$BACKUPARGS" "$BACKUPWAIT"
                    fi
                fi
            fi ;;
    esac
}

# ===== EXECUTE LAUNCH SEQUENCE =====
echo "Executing launch sequence: $LAUNCHSEQ"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing launch sequence: $LAUNCHSEQ" >> "$LOGFILE"
IFS=',' read -ra LAUNCH_ITEMS <<< "$LAUNCHSEQ"
for item in "${LAUNCH_ITEMS[@]}"; do
    item=$(echo "$item" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    execute_sequence_item "$item" "launch"
done

# ===== JUST AFTER LAUNCH APP =====
[ -n "$JUSTAFTERAPP" ] && echo "Running Just After Launch app..." && run_app "$JUSTAFTERAPP" "$JUSTAFTEROPTS" "$JUSTAFTERARGS" "$JUSTAFTERWAIT"

# ===== LAUNCH GAME =====
echo "Launching game: $GAMENAME"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching game: $GAMENAME" >> "$LOGFILE"
cd "$GAMEDIR"
[ ! -x "$GAMEPATH" ] && chmod +x "$GAMEPATH" 2>/dev/null || true
if [[ "$RUNASADMIN" =~ ^[1Tt] ]]; then
    echo "Running with elevated privileges..."
    command -v sudo &> /dev/null && sudo "$GAMEPATH" || "$GAMEPATH"
else
    "$GAMEPATH"
fi
echo "Game exited"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Game exited" >> "$LOGFILE"

# ===== JUST BEFORE EXIT APP =====
[ -n "$JUSTBEFOREAPP" ] && echo "Running Just Before Exit app..." && run_app "$JUSTBEFOREAPP" "$JUSTBEFOREOPTS" "$JUSTBEFOREARGS" "$JUSTBEFOREWAIT"

# ===== EXECUTE EXIT SEQUENCE =====
echo "Executing exit sequence: $EXITSEQ"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing exit sequence: $EXITSEQ" >> "$LOGFILE"
IFS=',' read -ra EXIT_ITEMS <<< "$EXITSEQ"
for item in "${EXIT_ITEMS[@]}"; do
    item=$(echo "$item" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    execute_sequence_item "$item" "exit"
done

# ===== KILL PROCESSES FROM KILL LIST =====
if [[ "$USEKILLLIST" =~ ^[1Tt] ]] && [ -n "$KILLLIST" ]; then
    echo "Killing processes from kill list..."
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Killing processes from kill list: $KILLLIST" >> "$LOGFILE"
    IFS=',' read -ra PROCESSES <<< "$KILLLIST"
    for proc in "${PROCESSES[@]}"; do
        proc=$(echo "$proc" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -n "$proc" ] && echo "  Killing: $proc" && pkill -f "$proc" 2>/dev/null || true
    done
fi

echo "Launcher finished"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launcher finished" >> "$LOGFILE"
exit 0
