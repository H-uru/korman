#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

param(
    [Parameter(ParameterSetName="classic", Mandatory=$false)]
    [Parameter(ParameterSetName="modern", Mandatory=$false)]
    [Parameter(ParameterSetName="dev", Mandatory=$false)]
    [ValidateSet("Visual Studio 2013", "Visual Studio 2015", "Visual Studio 2017", "Visual Studio 2019", "Visual Studio 2022")]
    [string]$Generator,

    [Parameter(ParameterSetName="classic", Mandatory=$false)]
    [Parameter(ParameterSetName="modern", Mandatory=$false)]
    [Parameter(ParameterSetName="dev", Mandatory=$false)]
    [string]$BuildDir = "$(Get-Location)/build",

    [Parameter(ParameterSetName="modern", Mandatory=$true)]
    [ValidateScript({
        if (Get-Command cpack) {
            $true
        } else {
            throw "Modern requires that CPack be installed and available on the PATH."
        }
    })]
    [switch]$Modern,

    [Parameter(ParameterSetName="classic", Mandatory=$true)]
    [ValidateScript({
        if (Get-Command makensis) {
            $true
        } else {
            throw "Classic requires that NSIS be installed and available on the PATH."
        }
    })]
    [switch]$Classic,

    [Parameter(ParameterSetName="dev", Mandatory=$true)]
    [switch]$Dev,

    [Parameter(ParameterSetName="classic", Mandatory=$true)]
    [Parameter(ParameterSetName="dev", Mandatory=$false)]
    [string]$PythonVersion,

    [Parameter(ParameterSetName="modern")]
    [ValidateSet("x86", "x64")]
    [string]$Platform,

    [Parameter(ParameterSetName="modern")]
    [Parameter(ParameterSetName="dev")]
    [string]$BlenderDir,

    [Parameter(ParameterSetName="modern")]
    [switch]$NoInstaller,

    [Parameter(ParameterSetName="modern")]
    [switch]$NoBlender,

    [Parameter(ParameterSetName="classic")]
    [Parameter(ParameterSetName="modern")]
    [switch]$RebuildDeps
)

# Enable for prod
$ErrorActionPreference = "Stop"

$Generator_LUT = @{
    "Visual Studio 2013" = "Visual Studio 12 2013"
    "Visual Studio 2015" = "Visual Studio 14 2015"
    "Visual Studio 2017" = "Visual Studio 15 2017"
    "Visual Studio 2019" = "Visual Studio 16 2019"
    "Visual Studio 2022" = "Visual Studio 17 2022"
};

$Platform_LUT = @{
    "x86" = "Win32"
    "x64" = "x64"
}

# Fixup -NoBlender for dev and classic modes.
if ($Classic -Or $Dev) {
    $NoBlender = $true
}

function Find-CMakeArgument($UserInput, $EnvValue, $LUT, $Default) {
    if ($UserInput) {
        return $LUT[$UserInput]
    }
    if ($EnvValue) {
        return $EnvValue
    }
    return $Default
}

function Convert-BoolToCMake($Value) {
    if ($Value) {
        "ON"
    } else {
        "OFF"
    }
}

function Start-KormanBuild($HostGenerator, $TargetPlatform, $OutputDir, $StagingDir) {
    # Only pass the -G and -A arguments for new build directories.
    if (!(Test-Path "$OutputDir/CMakeCache.txt")) {
        Write-Host -ForegroundColor Cyan "Configuring Korman with $HostGenerator for $TargetPlatform..."
        $GeneratorArg = "-G$HostGenerator"
        $PlatformArg = "-A$TargetPlatform"
    } else {
        Write-Host -ForegroundColor Cyan "Re-Configuring Korman..."
    }
    $InstallBlender = Convert-BoolToCMake $(if ($NoBlender) { $false } else { $true })
    $HarvestPython22 = Convert-BoolToCMake $(if ($NoInstaller) { $false } else { $true })
    cmake `
        $GeneratorArg $PlatformArg `
        -S "$PSScriptRoot" `
        -B "$OutputDir" `
        -DBlender_ROOT="$BlenderDir" `
        -DBlender_PYTHON_VERSION="$PythonVersion" `
        -Dkorman_EXTERNAL_STAGING_DIR="$StagingDir" `
        -Dkorman_HARVEST_PYTHON22="$HarvestPython22" `
        -Dkorman_INSTALL_BLENDER="$InstallBlender"
    if ($LASTEXITCODE -Ne 0) { throw "Configure failed!" }
}

function Set-KormanClassicBuild($OutputDir, $Arch) {
    Write-Host -ForegroundColor Cyan "Setting up classic multi-arch build..."
    cmake `
        -B "$OutputDir" `
        -Dkorman_INSTALL_BLENDER=OFF `
        -Dkorman_INSTALL_SCRIPTS=OFF `
        -Dkorman_INSTALL_BINARY_DIR="$PSScriptRoot/installer/Files/$Arch"
    if ($LASTEXITCODE -Ne 0) { throw "Configure failed!" }
}

function Set-KormanDevBuild($OutputDir) {
    Write-Host -ForegroundColor Cyan "Setting up development build..."
    if ($BlenderDir) { $InstallDest = $BlenderDir } else { $InstallDest = "$OutputDir/install" }
    cmake `
        -B "$OutputDir" `
        -DCMAKE_INSTALL_PREFIX="$InstallDest" `
        -Dkorman_HARVEST_PYTHON22=OFF `
        -Dkorman_HARVEST_VCREDIST=OFF `
        -Dkorman_INSTALL_BLENDER=OFF `
        -Dkorman_INSTALL_SCRIPTS=OFF `
        -Dkorman_INSTALL_PACKAGE=OFF
}

function Complete-KormanBuild($OutputDir, $Install = $false) {
    Write-Host -ForegroundColor Cyan "Aaaand they're off!!!"
    # Don't even ask.
    if ($Install) {
        cmake --build `"$OutputDir`" --target INSTALL --config Release --parallel
    } else {
        cmake --build `"$OutputDir`" @($InstallArg) --config Release --parallel
    }
    if ($LASTEXITCODE -Ne 0) { throw "Build failed!" }
}

function Build-KormanClassicSingleArch($HostGenerator, $TargetPlatform, $OutputDir) {
    $MyPlatform = $Platform_LUT[$TargetPlatform]
    $MyBuildDir = "$OutputDir/$TargetPlatform"
    $CheckBuildDir = Test-Path $MyBuildDir
    Start-KormanBuild "$HostGenerator" "$MyPlatform" "$MyBuildDir" "$OutputDir/external"
    Set-KormanClassicBuild "$MyBuildDir" "$TargetPlatform"
    if (!$CheckBuildDir -Or $RebuildDeps) {
        Complete-KormanBuild "$MyBuildDir"
    }
}

function Build-KormanClassicInstaller() {
    # Ugh, CMake is nice enough to do this kind of shit for us.
    New-Item -Path "$PSScriptRoot/installer/Files/x86" -ItemType Directory -Force
    New-Item -Path "$PSScriptRoot/installer/Files/x64" -ItemType Directory -Force

    # CMake copies the vcredist for us. YAY!
    Write-Host -ForegroundColor Cyan "Copying sub-installers..."
    Copy-Item "$BuildDir/x86/harvest/bin/vcredist_x86.exe" "$PSScriptRoot/installer/Files/x86/vcredist_x86.exe"
    Copy-Item "$BuildDir/x64/harvest/bin/vcredist_x64.exe" "$PSScriptRoot/installer/Files/x64/vcredist_x64.exe"
    Copy-Item "$BuildDir/x86/harvest/bin/Python-2.2.3.exe" "$PSScriptRoot/installer/Files/x86/Python-2.2.3.exe"

    Write-Host -ForegroundColor Cyan "Determining Build Info..."
    if (Get-Command git) {
        Push-Location "$PSScriptRoot"
        try {
            $KormanRev = git describe --tags --dirty
        } finally {
            Pop-Location
        }
    } else {
        $KormanRev = "untracked"
    }

    Write-Host -ForegroundColor Cyan "Building NSIS installer..."
    Push-Location installer
    try {
        $PythonDLL = "python$($PythonVersion.Replace('.', '')).dll"
        makensis /DPYTHON_DLL=$PythonDLL Installer.nsi
        if ($LASTEXITCODE -Ne 0) { throw "makensis failed!" }

        # Move it into the expected location for a "new" installer.
        New-Item -Path "$BuildDir/package" -ItemType Directory -Force
        Move-Item "$PSScriptRoot/installer/korman.exe" "$BuildDir/package/korman-$KormanRev-windows-classic.exe"
    } finally {
        Pop-Location
    }
}

function Build-KormanDev($HostGenerator, $TargetPlatform, $OutputDir) {
    Start-KormanBuild "$HostGenerator" "$TargetPlatform" "$OutputDir" "$OutputDir/external"
    Set-KormanDevBuild "$OutputDir"
    Complete-KormanBuild "$OutputDir" -Install $true
}

function Build-KormanModern($HostGenerator, $TargetPlatform, $OutputDir) {
    $CheckBuildDir = Test-Path $OutputDir
    Start-KormanBuild "$HostGenerator" "$TargetPlatform" "$OutputDir" "$OutputDir/external"
    if (!$CheckBuildDir -Or $RebuildDeps) {
        Complete-KormanBuild "$OutputDir"
    }

    if ($NoInstaller) {
        $CPackGenerator = "ZIP"
    } else {
        $CPackGenerator = "WIX;ZIP"
    }

    Push-Location "$BuildDir"
    try {
        cpack `
            -G "$CPackGenerator" `
            -C Release
        if ($LASTEXITCODE -Eq 0) {
            Remove-Item -Recurse -Force "$BuildDir/package/_CPack_Packages"
        }
    } finally {
        Pop-Location
    }
}

try {
    Get-Command cmake | Out-Null
} catch {
    throw "CMake must be installed and available on the PATH."
}

$MyGenerator = Find-CMakeArgument $Generator $Env:CMAKE_GENERATOR $Generator_LUT "Visual Studio 16 2019"
if ($Classic) {
    Build-KormanClassicSingleArch "$MyGenerator" x86 "$BuildDir"
    Build-KormanClassicSingleArch "$MyGenerator" x64 "$BuildDir"
    Build-KormanClassicInstaller
} elseif($Modern) {
    $MyPlatform = Find-CMakeArgument $Platform $Env:CMAKE_GENERATOR_PLATFORM $Platform_LUT x64
    Build-KormanModern "$MyGenerator" "$MyPlatform" "$BuildDir"
} elseif($Dev) {
    $MyPlatform = Find-CMakeArgument $Platform $Env:CMAKE_GENERATOR_PLATFORM $Platform_LUT x64
    Build-KormanDev "$MyGenerator" "$MyPlatform" "$BuildDir"
} else {
    throw "Unknown build type"
}
