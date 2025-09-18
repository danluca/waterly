pushd $PSScriptRoot

Remove-Item ./build -Recurse -Force -ErrorAction SilentlyContinue
npm run build
remove-item ../src/web/static/js -Recurse -Force -ErrorAction SilentlyContinue
copy-item ./build/index.html ../src/web/static/index.html -Force
copy-item ./build/static/js ../src/web/static -Recurse -Force
copy-item ./build/asset-manifest.json ../src/web/static/asset-manifest.json -Force

popd