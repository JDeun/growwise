fn external_http_url(value: &str) -> Result<String, String> {
    if value.is_empty()
        || value.len() > 8192
        || value
            .chars()
            .any(|character| character.is_control() || character.is_whitespace())
    {
        return Err("올바른 HTTP(S) 출처 주소가 아닙니다.".to_string());
    }
    let url = reqwest::Url::parse(value)
        .map_err(|_| "올바른 HTTP(S) 출처 주소가 아닙니다.".to_string())?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err("로그인 정보가 없는 HTTP(S) 출처 주소만 열 수 있습니다.".to_string());
    }
    Ok(url.into())
}

#[tauri::command]
pub(crate) async fn open_external_url(url: String) -> Result<(), String> {
    let url = external_http_url(&url)?;
    let failure = "기본 브라우저를 열지 못했습니다. 브라우저 설정을 확인하고 다시 시도해 주세요.";
    tauri::async_runtime::spawn_blocking(move || open::that(url))
        .await
        .map_err(|_| failure.to_string())?
        .map_err(|_| failure.to_string())
}

#[cfg(test)]
mod tests {
    use super::external_http_url;

    #[test]
    #[ignore = "opens the OS default browser; requires an interactive desktop session"]
    fn native_default_browser_opens_public_example_source() {
        let result = tauri::async_runtime::block_on(super::open_external_url(
            "https://example.org".to_string(),
        ));
        assert!(result.is_ok(), "{}", result.unwrap_err());
    }

    #[test]
    fn permits_only_http_sources_without_credentials_or_raw_control_characters() {
        for url in [
            "https://example.org/source?q=seed#details",
            "http://example.org/article",
            "https://example.org/%EC%94%A8%EC%95%97",
        ] {
            assert!(external_http_url(url).is_ok(), "{url}");
        }
        for url in [
            "",
            "file:///private/secret",
            "javascript:alert(1)",
            "mailto:test@example.org",
            "https://user:password@example.org/",
            "https://user@example.org/",
            "https://example.org/\nsource",
            "https://example.org/\tsource",
            " https://example.org/",
            "https://example.org/a b",
            "https://example.org/\u{0085}source",
        ] {
            assert!(external_http_url(url).is_err());
        }
    }
}
