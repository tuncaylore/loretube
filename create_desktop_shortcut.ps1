param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectDir = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'

function New-YouTubeStyleIcon {
    param([string]$Path)

    Add-Type -AssemblyName System.Drawing

    $bitmap = New-Object System.Drawing.Bitmap 256, 256, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $pathShape = New-Object System.Drawing.Drawing2D.GraphicsPath
    $stream = New-Object System.IO.MemoryStream
    $writer = $null

    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.Clear([System.Drawing.Color]::Transparent)

        $pathShape.AddArc(20, 20, 64, 64, 180, 90)
        $pathShape.AddArc(172, 20, 64, 64, 270, 90)
        $pathShape.AddArc(172, 172, 64, 64, 0, 90)
        $pathShape.AddArc(20, 172, 64, 64, 90, 90)
        $pathShape.CloseFigure()

        $redBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 235, 35, 45))
        $graphics.FillPath($redBrush, $pathShape)
        $redBrush.Dispose()

        $playTriangle = [System.Drawing.Point[]]@(
            [System.Drawing.Point]::new(104, 76),
            [System.Drawing.Point]::new(104, 180),
            [System.Drawing.Point]::new(184, 128)
        )
        $whiteBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
        $graphics.FillPolygon($whiteBrush, $playTriangle)
        $whiteBrush.Dispose()

        $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
        $pngBytes = $stream.ToArray()

        $writer = New-Object System.IO.BinaryWriter ([System.IO.File]::Open($Path, [System.IO.FileMode]::Create))
        $writer.Write([UInt16]0)          # Reserved
        $writer.Write([UInt16]1)          # ICO resource type
        $writer.Write([UInt16]1)          # Image count
        $writer.Write([Byte]0)            # Width: 0 means 256 px
        $writer.Write([Byte]0)            # Height: 0 means 256 px
        $writer.Write([Byte]0)            # Palette
        $writer.Write([Byte]0)            # Reserved
        $writer.Write([UInt16]1)          # Color planes
        $writer.Write([UInt16]32)         # Bits per pixel
        $writer.Write([UInt32]$pngBytes.Length)
        $writer.Write([UInt32]22)         # Image data offset
        $writer.Write($pngBytes)
    }
    finally {
        if ($writer) { $writer.Dispose() }
        $stream.Dispose()
        $pathShape.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

try {
    $project = (Resolve-Path -LiteralPath $ProjectDir).Path
    $desktop = [Environment]::GetFolderPath('DesktopDirectory')
    if ([string]::IsNullOrWhiteSpace($desktop) -or -not (Test-Path -LiteralPath $desktop -PathType Container)) {
        throw 'Windows masaustu klasoru bulunamadi.'
    }

    $iconDirectory = Join-Path $project 'tools'
    if (-not (Test-Path -LiteralPath $iconDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $iconDirectory -Force | Out-Null
    }
    $iconPath = Join-Path $iconDirectory 'tubeflow-youtube.ico'
    New-YouTubeStyleIcon -Path $iconPath

    $shortcutPath = Join-Path $desktop 'TubeFlow - YouTube Baslat.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $project 'run.bat'
    $shortcut.WorkingDirectory = $project
    $shortcut.Description = 'TubeFlow YouTube indiricisini baslat'
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Save()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)

    Write-Output "Masaustu kisayolu hazir: $shortcutPath"
    exit 0
}
catch {
    [Console]::Error.WriteLine("Masaustu kisayolu olusturulamadi: $($_.Exception.Message)")
    exit 1
}
