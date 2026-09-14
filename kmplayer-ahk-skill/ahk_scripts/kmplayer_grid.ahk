; -----------------------------
; kmplayer_grid.ahk
; -----------------------------

; Parameters passed from Python
videoPath := A_Args[1]       ; Video file path
outputPath := A_Args[2]      ; Folder to save screenshots
kmplayerPath := "C:\KMPlayer\KMPlayer.exe"
capturePath := "C:\KMPlayer\Capture"

; Log file
logFile := outputPath "\log.txt"

nameNoExt := ""
SplitPath(videoPath, &fileName, &dir, &ext, &nameNoExt)
screenshotFile := capturePath "\" nameNoExt ".JPG"
targetFile := outputPath "\" nameNoExt ".JPG"

; Check if video exists
if !FileExist(videoPath)
{
    FileAppend(Format("[{1}] Video not found: {2}`n", A_Now, videoPath), logFile)
    ExitApp
}

; -----------------------------
; Close any existing KMPlayer process
; -----------------------------
if WinExist("ahk_exe KMPlayer.exe")
{
    FileAppend(Format("[{1}] KMPlayer already exist`n", A_Now), logFile)
    WinClose()
    WinWaitClose("ahk_exe KMPlayer.exe", , 5)
}

; -----------------------------
; Launch KMPlayer and open video
; -----------------------------
Run(kmplayerPath ' "' videoPath '"')

if WinWait("ahk_class KMPlayer Ext", , 20)
{
    WinActivate("ahk_class KMPlayer Ext")
    Sleep(200)

    ; Send the capture shortcut Ctrl+Shift+S
    Send("^+s")

    ; Wait up to 5 seconds for the capture confirmation dialog, then click OK
    if WinWait("ahk_class TSnapShotForm", , 5)
    {
        WinActivate("ahk_class TSnapShotForm")
        Sleep(200)
        ControlClick("TButton2", "ahk_class TSnapShotForm")  ; Click OK
    }

    if WinWait("ahk_class TTntMessageForm",, 30)
        ControlClick("TButton1", "ahk_class TTntMessageForm")

    ; Write to the log
    if FileExist(screenshotFile)
    {
        FileMove(screenshotFile, targetFile, true)  ; true overwrites the target if it exists
        FileAppend(Format("[{1}] Capture success: {2}`n", A_Now, screenshotFile), logFile)
    }
    else
    {
        FileAppend(Format("[{1}] Capture error: {2}`n", A_Now, screenshotFile), logFile)
    }

    ; Close KMPlayer
    if WinExist("ahk_exe KMPlayer.exe")
    {
        FileAppend(Format("[{1}]WinExist`r`n", A_Now), logFile)
        ; Try to close gracefully
        WinClose("ahk_exe KMPlayer.exe")
        FileAppend(Format("[{1}]WinClose`r`n", A_Now), logFile)
        ; Wait up to 5 seconds for the window to close
        if !WinWaitClose("ahk_exe KMPlayer.exe", , 5)
        {
            ; Force termination if the window still exists
            FileAppend(Format("[{1}]KMPlayer is not responding; forcing it to close...`r`n", A_Now), logFile)
            WinKill("ahk_exe KMPlayer.exe")
        }
    }
    ExitApp
}
else
{
    ; MsgBox "The KMPlayer window did not open or timed out!"
    FileAppend(Format("[{1}] KMPlayer did not start or timed out`r`n", A_Now), logFile)
}

ExitApp
