# PPTX -> PDF through PowerPoint COM.
#
# The Windows sandbox blocks COM (0x80070005 / E_ACCESSDENIED), so this one step must
# run with sandbox_permissions = danger-full-access. Everything else stays confined.
#
#   pwsh -File pptx2pdf.ps1 -Src "C:\deck.pptx" -Dst "C:\work\deck.pdf"
#   pwsh -File pptx2pdf.ps1 -Src "src" -Dst "dst" -PptxToPdf      # batch: every .pptx in -Src

param(
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$Dst,
    [switch]$PptxToPdf
)

$ErrorActionPreference = 'Stop'

function Convert-One($inPath, $outPath) {
    $app = New-Object -ComObject PowerPoint.Application
    try {
        $pres = $app.Presentations.Open($inPath, $true, $false, $false)
        try {
            $pres.SaveAs($outPath, 32)          # 32 = ppSaveAsPDF
        }
        finally {
            $pres.Close()
        }
    }
    finally {
        $app.Quit()
    }
    Write-Output "saved $outPath"
}

if ($PptxToPdf) {
    if (-not (Test-Path $Dst)) { New-Item -ItemType Directory -Path $Dst | Out-Null }
    Get-ChildItem -Path $Src -Filter *.pptx | ForEach-Object {
        $out = Join-Path $Dst ($_.BaseName + '.pdf')
        Convert-One $_.FullName $out
    }
}
else {
    Convert-One $Src $Dst
}
