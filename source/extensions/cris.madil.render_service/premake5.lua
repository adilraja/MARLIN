-- CRIS Render Service extension

local ext = get_current_extension_info()

project_ext(ext)

repo_build.prebuild_link {
    { "config", ext.target_dir.."/config" },
    { "data", ext.target_dir.."/data" },
    { "docs", ext.target_dir.."/docs" },
    { "cris", ext.target_dir.."/cris" },
}
