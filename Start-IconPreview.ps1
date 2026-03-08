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

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "Python not found in PATH. Install Python 3.11+ and try again."
}

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

& $pythonCmd.Source @argsList
