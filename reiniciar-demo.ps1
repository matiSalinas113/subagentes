# Limpia artefactos temporales sin restaurar código vulnerable ni eliminar documentación o pruebas.
$raiz = $PSScriptRoot
Remove-Item "$raiz\proyecto-demo\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Artefactos temporales limpiados; el código seguro, las pruebas y el README se conservaron."
