param(
    [Parameter(Mandatory = $true)]
    [string]$Reference,

    [string]$Entities,

    [string]$EntitiesFile,

    [string]$Output,

    [string]$SessionName,

    [string]$Config = "config.json",

    [switch]$Force
)

function Resolve-PythonExe {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidatePaths = @(
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )

    foreach ($path in $candidatePaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    throw "Python not found. Install Python 3.11+ and ensure python.exe is available."
}

$pythonExe = Resolve-PythonExe

$argsList = @("-m", "app.main", "one-click", "--reference", $Reference, "--config", $Config)

if ($Entities) {
    $argsList += @("--entities", $Entities)
}
if ($EntitiesFile) {
    $argsList += @("--entities-file", $EntitiesFile)
}
if ($Output) {
    $argsList += @("--output", $Output)
}
if ($SessionName) {
    $argsList += @("--session-name", $SessionName)
}
if ($Force) {
    $argsList += "--force"
}

& $pythonExe @argsList
