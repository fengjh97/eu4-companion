# 把 EU4 军师 的 Chrome app 窗口设为「始终置顶」，好贴在游戏上方。
# 用法：游戏开「无边框窗口化」，面板窗口开着，然后右键此文件 -> 用 PowerShell 运行。
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h,IntPtr a,int x,int y,int cx,int cy,uint f);
}
"@
$HWND_TOPMOST = [IntPtr](-1)
$SWP = 0x0001 -bor 0x0002  # NOSIZE | NOMOVE
# 找标题含 "EU4 军师" 的窗口
$found = $false
Get-Process | Where-Object { $_.MainWindowTitle -match "EU4 军师|EU4 军师 -|localhost|127.0.0.1" } | ForEach-Object {
  if ($_.MainWindowHandle -ne 0) {
    [Win]::SetWindowPos($_.MainWindowHandle,$HWND_TOPMOST,0,0,0,0,$SWP) | Out-Null
    Write-Host ("已置顶: " + $_.MainWindowTitle)
    $found = $true
  }
}
if (-not $found) { Write-Host "没找到面板窗口。确认 Chrome app 窗口开着、标题是 'EU4 军师'。" }
