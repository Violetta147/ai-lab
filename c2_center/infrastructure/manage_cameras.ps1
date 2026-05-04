#!/usr/bin/env pwsh
# C2 Surveillance Center - Interactive Camera Manager
# Screen 1: Add, edit, enable/disable, delete any cameras
# All changes sync to backend immediately.

param(
    [string]$ApiBase = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Show-Menu {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  C2 SURVEILLANCE CENTER" -ForegroundColor Cyan
    Write-Host "  Camera Management System" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [1] List all cameras" -ForegroundColor White
    Write-Host "  [2] Add new camera" -ForegroundColor Green
    Write-Host "  [3] Edit camera" -ForegroundColor Yellow
    Write-Host "  [4] Enable/Disable camera" -ForegroundColor Yellow
    Write-Host "  [5] Delete camera" -ForegroundColor Red
    Write-Host "  [6] Start/Stop camera publishers" -ForegroundColor Magenta
    Write-Host "  [0] Exit" -ForegroundColor Gray
    Write-Host ""
}

function Get-Cameras {
    try {
        $response = Invoke-RestMethod -Uri "$ApiBase/api/cameras" -Method GET
        return $response.cameras
    }
    catch {
        Write-Host "[ERROR] Cannot reach backend at $ApiBase" -ForegroundColor Red
        Write-Host "  Is the backend running? Try: uvicorn main:app --host 0.0.0.0 --port 8000" -ForegroundColor DarkGray
        return @()
    }
}

function Show-Cameras {
    $cameras = Get-Cameras
    if ($cameras.Count -eq 0) {
        Write-Host "  No cameras configured." -ForegroundColor Gray
        return
    }

    Write-Host ""
    Write-Host "CAMERAS:" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Gray
    for ($i = 0; $i -lt $cameras.Count; $i++) {
        $cam = $cameras[$i]
        $status = if ($cam.enabled) { "[ON] " } else { "[OFF]" }
        Write-Host "  [$($i+1)] $($cam.stream_id)" -ForegroundColor White -NoNewline
        Write-Host " $status" -ForegroundColor $(if ($cam.enabled) {"Green"} else {"Gray"})
        Write-Host "       RTSP: $($cam.rtsp_url)" -ForegroundColor DarkGray
        Write-Host "       Name: $($cam.name)" -ForegroundColor DarkGray
        if ($cam.description) {
            Write-Host "       Desc: $($cam.description)" -ForegroundColor DarkGray
        }
    }
    Write-Host "======================================================================" -ForegroundColor Gray
}

function Add-Camera {
    Write-Host ""
    Write-Host "ADD NEW CAMERA" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Gray

    $streamId = Read-Host "  Stream ID (e.g., parking_lot_1)"
    if (-not $streamId) {
        Write-Host "  [SKIP] Empty stream ID" -ForegroundColor Yellow
        return
    }

    $rtspUrl = Read-Host "  RTSP URL (e.g., rtsp://localhost:8554/cam_parking1)"
    if (-not $rtspUrl) {
        Write-Host "  [SKIP] Empty RTSP URL" -ForegroundColor Yellow
        return
    }

    $name = Read-Host "  Display name (e.g., Parking Lot - Zone 1)"
    if (-not $name) {
        $name = $streamId
    }

    $description = Read-Host "  Description (optional, press Enter to skip)"

    $body = @{
        stream_id   = $streamId
        rtsp_url    = $rtspUrl
        name        = $name
        description = $description
        enabled     = $true
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod -Uri "$ApiBase/api/cameras" -Method POST `
            -ContentType "application/json" -Body $body
        Write-Host "  [OK] Camera added: $($response.camera.stream_id)" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to add camera" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor DarkGray
    }
}

function Edit-Camera {
    Write-Host ""
    Write-Host "EDIT CAMERA" -ForegroundColor Yellow
    Write-Host "======================================================================" -ForegroundColor Gray

    Show-Cameras
    
    $streamId = Read-Host "`n  Enter stream ID to edit"
    if (-not $streamId) {
        Write-Host "  [SKIP] Empty input" -ForegroundColor Yellow
        return
    }

    try {
        $cam = Invoke-RestMethod -Uri "$ApiBase/api/cameras/$streamId" -Method GET
        
        Write-Host "`n  Current name: $($cam.name)" -ForegroundColor Gray
        $newName = Read-Host "  New name (press Enter to keep)"
        
        Write-Host "  Current URL: $($cam.rtsp_url)" -ForegroundColor Gray
        $newUrl = Read-Host "  New RTSP URL (press Enter to keep)"
        
        Write-Host "  Current desc: $($cam.description)" -ForegroundColor Gray
        $newDesc = Read-Host "  New description (press Enter to keep)"

        $updates = @{}
        if ($newName) { $updates["name"] = $newName }
        if ($newUrl) { $updates["rtsp_url"] = $newUrl }
        if ($newDesc) { $updates["description"] = $newDesc }

        if ($updates.Count -eq 0) {
            Write-Host "  [SKIP] No changes" -ForegroundColor Yellow
            return
        }

        $body = $updates | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$ApiBase/api/cameras/$streamId" -Method PUT `
            -ContentType "application/json" -Body $body

        Write-Host "  [OK] Camera updated: $streamId" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Camera not found or update failed" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor DarkGray
    }
}

function Toggle-Camera {
    Write-Host ""
    Write-Host "ENABLE / DISABLE CAMERA" -ForegroundColor Yellow
    Write-Host "======================================================================" -ForegroundColor Gray

    Show-Cameras
    
    $streamId = Read-Host "`n  Enter stream ID to toggle"
    if (-not $streamId) {
        Write-Host "  [SKIP] Empty input" -ForegroundColor Yellow
        return
    }

    try {
        $cam = Invoke-RestMethod -Uri "$ApiBase/api/cameras/$streamId" -Method GET
        $newState = -not $cam.enabled
        $action = if ($newState) { "ENABLED" } else { "DISABLED" }
        
        $body = @{ enabled = $newState } | ConvertTo-Json
        Invoke-RestMethod -Uri "$ApiBase/api/cameras/$streamId" -Method PUT `
            -ContentType "application/json" -Body $body | Out-Null

        Write-Host "  [OK] Camera $($action): $streamId" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to toggle camera" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor DarkGray
    }
}

function Delete-Camera {
    Write-Host ""
    Write-Host "DELETE CAMERA" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Gray

    Show-Cameras
    
    $streamId = Read-Host "`n  Enter stream ID to DELETE (type exactly to confirm)"
    if (-not $streamId) {
        Write-Host "  [SKIP] Empty input" -ForegroundColor Yellow
        return
    }

    $confirm = Read-Host "  Type YES to confirm deletion of $streamId"
    if ($confirm -ne "YES") {
        Write-Host "  [CANCEL] Deletion aborted" -ForegroundColor Yellow
        return
    }

    try {
        Invoke-RestMethod -Uri "$ApiBase/api/cameras/$streamId" -Method DELETE | Out-Null
        Write-Host "  [OK] Camera deleted: $streamId" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to delete camera" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor DarkGray
    }
}

function Start-Publishers {
    Write-Host ""
    Write-Host "START CAMERA PUBLISHERS" -ForegroundColor Magenta
    Write-Host "======================================================================" -ForegroundColor Gray
    
    $script = "..\infrastructure\publish_cameras_dynamic.ps1"
    if (-not (Test-Path $script)) {
        Write-Host "  [ERROR] Publisher script not found at $script" -ForegroundColor Red
        return
    }

    $videoPath = Read-Host "  Video file path (press Enter for default: D:\datas\Final.yolov8\density\test_video.mp4)"
    if (-not $videoPath) {
        $videoPath = "D:\datas\Final.yolov8\density\test_video.mp4"
    }

    if (-not (Test-Path $videoPath)) {
        Write-Host "  [ERROR] Video file not found: $videoPath" -ForegroundColor Red
        return
    }

    Write-Host "  Starting publisher in new window..." -ForegroundColor Yellow
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", ". '$script' -VideoPath '$videoPath' -ApiBase '$ApiBase'"
    Write-Host "  [OK] Publisher window opened" -ForegroundColor Green
}

# Main loop
Write-Host ""
Write-Host "C2 SURVEILLANCE CAMERA MANAGER" -ForegroundColor Cyan
Write-Host "Connecting to backend: $ApiBase" -ForegroundColor Gray
Write-Host ""

$null = Get-Cameras  # Test connection

while ($true) {
    Show-Menu
    $choice = Read-Host "  Select option"

    switch ($choice) {
        "1" { Show-Cameras }
        "2" { Add-Camera }
        "3" { Edit-Camera }
        "4" { Toggle-Camera }
        "5" { Delete-Camera }
        "6" { Start-Publishers }
        "0" {
            Write-Host ""
            Write-Host "Goodbye!" -ForegroundColor Cyan
            exit 0
        }
        default {
            Write-Host "  [ERROR] Invalid option" -ForegroundColor Red
        }
    }
}
