$ErrorActionPreference = "Stop"

Push-Location web
npm install
npm run build
Pop-Location

New-Item -ItemType Directory -Force -Path server/public | Out-Null
Copy-Item -Recurse -Force web/dist/* server/public/

go build -o tavily-proxy.exe ./server
Write-Host "Built: tavily-proxy.exe"
