# Building web frontend...
Write-Host "Building web frontend..."
Set-Location "$PSScriptRoot/../web"
npm install
npm run build

# Preparing server public directory...
Write-Host "Preparing server public directory..."
$publicDir = "$PSScriptRoot/../server/public"
if (!(Test-Path $publicDir)) {
    New-Item -ItemType Directory -Path $publicDir
}
Remove-Item -Path "$publicDir/*" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$PSScriptRoot/../web/dist/*" -Destination $publicDir -Recurse

# Create build directory
$buildDir = "$PSScriptRoot/../build"
if (!(Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir
}

# Building Windows binary...
Write-Host "Building Windows binary..."
Set-Location "$PSScriptRoot/../server"
$env:CGO_ENABLED = "0"
$env:GOOS = "windows"
$env:GOARCH = "amd64"
go build -o "$buildDir/tavily-proxy-win.exe" main.go

# Building Linux binary...
Write-Host "Building Linux binary..."
$env:CGO_ENABLED = "0"
$env:GOOS = "linux"
$env:GOARCH = "amd64"
go build -o "$buildDir/tavily-proxy-linux" main.go

Write-Host "Build complete! Binaries are in the build/ directory."
