$ErrorActionPreference = "Stop"

# Laptop-side helper:
# 1) Publish dataset video as RTSP source for Jetson input.
# 2) Record processed RTSP output from Jetson to local MP4.

param(
    [Parameter(Mandatory = $true)][string]$DatasetPath,
    [Parameter(Mandatory = $true)][string]$JetsonIp,
    [string]$JetsonOutMount = "ds-test",
    [int]$JetsonOutPort = 8555,
    [string]$OutputFile = ".\jetson_processed_output.mp4"
)

Write-Host "[DEBUG] DatasetPath=$DatasetPath"
Write-Host "[DEBUG] JetsonIp=$JetsonIp"
Write-Host "[DEBUG] OutputFile=$OutputFile"

if (-not (Test-Path -Path $DatasetPath)) {
    throw "Dataset file not found: $DatasetPath"
}

$JetsonOutUrl = "rtsp://$JetsonIp`:$JetsonOutPort/$JetsonOutMount"

Write-Host ""
Write-Host "[DEBUG] Step 1: Start RTSP source on laptop (run in terminal A)"
Write-Host "ffmpeg -re -stream_loop -1 -i `"$DatasetPath`" -c copy -f rtsp rtsp://localhost:8554/mystream"
Write-Host ""
Write-Host "[DEBUG] Step 2: Record Jetson processed RTSP (run in terminal B)"
Write-Host "ffmpeg -rtsp_transport tcp -i `"$JetsonOutUrl`" -c copy `"$OutputFile`""
Write-Host ""
Write-Host "[DEBUG] Suggested VLC live monitor URL:"
Write-Host $JetsonOutUrl
