param(
    [string]$CloudSdkConfig,
    [string]$GcloudPath
)

$ErrorActionPreference = "Stop"

if (-not $CloudSdkConfig) {
    throw "CloudSdkConfig is required."
}

if (-not $GcloudPath) {
    throw "GcloudPath is required."
}

New-Item -ItemType Directory -Force -Path $CloudSdkConfig | Out-Null
$env:CLOUDSDK_CONFIG = $CloudSdkConfig

$urlFile = Join-Path $CloudSdkConfig "auth_url.txt"
$codeFile = Join-Path $CloudSdkConfig "auth_code.txt"
$resultFile = Join-Path $CloudSdkConfig "auth_result.txt"
$stdoutFile = Join-Path $CloudSdkConfig "auth_stdout.txt"
$stderrFile = Join-Path $CloudSdkConfig "auth_stderr.txt"
$debugFile = Join-Path $CloudSdkConfig "auth_debug.txt"

function Write-DebugLog([string]$message) {
    Add-Content -Path $debugFile -Value ("[{0}] {1}" -f (Get-Date -Format "s"), $message) -Encoding UTF8
}

foreach ($path in @($urlFile, $codeFile, $resultFile, $stdoutFile, $stderrFile, $debugFile)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

Write-DebugLog "Script started."

$escapedGcloudPath = $GcloudPath.Replace('"', '""')
$escapedStdoutFile = $stdoutFile.Replace('"', '""')
$escapedStderrFile = $stderrFile.Replace('"', '""')
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $env:ComSpec
$psi.Arguments = ('/d /c ""{0}" auth login --no-launch-browser --brief 1>"{1}" 2>"{2}"""' -f $escapedGcloudPath, $escapedStdoutFile, $escapedStderrFile)
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables["CLOUDSDK_CONFIG"] = $CloudSdkConfig
Write-DebugLog "Prepared process start info."

$process = [System.Diagnostics.Process]::Start($psi)
$authUrl = $null
Write-DebugLog "Started child process with id $($process.Id)."

try {
    while (-not $process.HasExited -and -not $authUrl) {
        if (Test-Path $stderrFile) {
            $stderrContent = Get-Content -Path $stderrFile -Raw
            if ($stderrContent -match 'https://accounts\.google\.com/\S+') {
                $authUrl = $Matches[0].Trim()
                Set-Content -Path $urlFile -Value $authUrl -Encoding ASCII
                Write-DebugLog "Captured auth URL."
            }
        }

        Start-Sleep -Milliseconds 250
    }

    Write-DebugLog "Exited URL wait loop. hasExited=$($process.HasExited) authUrl=$([bool]$authUrl)"

    while (-not $process.HasExited) {
        if (Test-Path $codeFile) {
            $code = (Get-Content -Path $codeFile -Raw).Trim()
            if ($code) {
                $process.StandardInput.WriteLine($code)
                $process.StandardInput.Flush()
                Remove-Item $codeFile -Force
                Write-DebugLog "Submitted auth code."
            }
        }

        Start-Sleep -Milliseconds 250
    }

    Write-DebugLog "Child process exited with code $($process.ExitCode)."

    $stdoutContent = ""
    $stderrContent = ""

    if (Test-Path $stdoutFile) {
        $stdoutContent = (Get-Content -Path $stdoutFile -Raw).TrimEnd()
    }

    if (Test-Path $stderrFile) {
        $stderrContent = (Get-Content -Path $stderrFile -Raw).TrimEnd()
    }

    $result = @(
        "exit_code=$($process.ExitCode)"
        "url=$authUrl"
        "--- stdout ---"
        $stdoutContent
        "--- stderr ---"
        $stderrContent
    )

    Set-Content -Path $resultFile -Value $result -Encoding UTF8
    Write-DebugLog "Wrote result file."
}
catch {
    $failure = @(
        "exit_code=script_error"
        "url=$authUrl"
        "--- error ---"
        $_.Exception.Message
    )
    Set-Content -Path $resultFile -Value $failure -Encoding UTF8
    Write-DebugLog "Caught exception: $($_.Exception.Message)"
    throw
}
