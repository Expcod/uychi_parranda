# Odoo stiker agentini exe qilish.
#
#   .\build.ps1
#
# Natija: dist\OdooPrintAgent-YYYY-MM-DD.exe  (bitta fayl, Python kerak emas)
#
# Nomda bild sanasi turadi — sexda eski va yangi fayl adashib ketmasin.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$date = Get-Date -Format "yyyy-MM-dd"
$env:AGENT_BUILD_DATE = $date
$exe = "dist\OdooPrintAgent-$date.exe"

Write-Host "1/3  Kutubxonalar tekshirilmoqda..." -ForegroundColor Cyan
python -m pip install --quiet --upgrade pyinstaller pywin32
if (-not $?) { throw "pip o'rnatishda xato" }

Write-Host "2/3  Eski build tozalanmoqda..." -ForegroundColor Cyan
# dist\ ichida ishchining agent.ini va agent.log fayllari yotadi — papkani
# butunlay o'chirsak sozlama (server, parol, token) yo'qoladi. Shuning uchun
# faqat shu bildning exe sini olib tashlaymiz; oldingi sanalilar qoladi,
# nosozlik chiqsa ishchi eskisiga qaytib tura oladi.
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path $exe) { Remove-Item -Force $exe }

Write-Host "3/3  Exe yasalmoqda (1-2 daqiqa)..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm agent.spec
if (-not $?) { throw "PyInstaller xatosi" }

if (-not (Test-Path $exe)) { throw "Exe yaratilmadi" }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Tayyor: $exe  ($size MB)" -ForegroundColor Green
Write-Host "Shu faylni sexdagi kompyuterga ko'chiring." -ForegroundColor Green
