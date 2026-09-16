use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::str::FromStr;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

const CORE_ADDRESS: &str = "127.0.0.1:8765";
const CORE_TOKEN_ENV: &str = "GROWWISE_DESKTOP_CORE_TOKEN";
const CORE_TOKEN_FILE_ENV: &str = "GROWWISE_API_TOKEN_FILE";
const STARTUP_ATTEMPTS: usize = 80;
const STARTUP_INTERVAL: Duration = Duration::from_millis(100);

pub struct CoreProcessManager {
    child: Mutex<Option<Child>>,
}

impl CoreProcessManager {
    pub fn ensure_started(resource_dir: &Path, app_data_dir: &Path) -> Result<Self, String> {
        if core_is_reachable() {
            return Err(
                "GrowWise Core 포트(127.0.0.1:8765)가 이미 사용 중입니다. 다른 프로세스를 Core로 신뢰하지 않고 시작을 중단합니다."
                    .to_string(),
            );
        }

        fs::create_dir_all(app_data_dir)
            .map_err(|error| format!("GrowWise 앱 데이터 폴더를 준비할 수 없습니다: {error}"))?;
        let token_file = app_data_dir.join("core-session.token");
        let _ = fs::remove_file(&token_file);
        env::remove_var(CORE_TOKEN_ENV);

        let mut command = core_command(resource_dir)?;
        command.env(CORE_TOKEN_FILE_ENV, &token_file);
        command.stdin(Stdio::null());

        if cfg!(debug_assertions) {
            command.stdout(Stdio::inherit()).stderr(Stdio::inherit());
        } else {
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }

        let mut child = command
            .spawn()
            .map_err(|error| format!("GrowWise Core를 시작할 수 없습니다: {error}"))?;

        for _ in 0..STARTUP_ATTEMPTS {
            if let Some(token) = read_session_token(&token_file)? {
                if core_is_authenticated(&token) {
                    env::set_var(CORE_TOKEN_ENV, &token);
                    let _ = fs::remove_file(&token_file);
                    return Ok(Self {
                        child: Mutex::new(Some(child)),
                    });
                }
            }

            if let Some(status) = child
                .try_wait()
                .map_err(|error| format!("GrowWise Core 상태 확인 실패: {error}"))?
            {
                let _ = fs::remove_file(&token_file);
                return Err(format!(
                    "GrowWise Core가 준비되기 전에 종료되었습니다: {status}"
                ));
            }
            thread::sleep(STARTUP_INTERVAL);
        }

        let _ = child.kill();
        let _ = child.wait();
        let _ = fs::remove_file(&token_file);
        env::remove_var(CORE_TOKEN_ENV);
        Err("GrowWise Core 시작 제한 시간을 초과했습니다.".to_string())
    }

    pub fn started_by_desktop(&self) -> bool {
        self.child
            .lock()
            .map(|child| child.is_some())
            .unwrap_or(false)
    }
}

impl Drop for CoreProcessManager {
    fn drop(&mut self) {
        let Ok(child_slot) = self.child.get_mut() else {
            return;
        };
        if let Some(child) = child_slot.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *child_slot = None;
        env::remove_var(CORE_TOKEN_ENV);
    }
}

fn core_command(resource_dir: &Path) -> Result<Command, String> {
    if let Ok(executable) = env::var("GROWWISE_CORE_EXECUTABLE") {
        if executable.trim().is_empty() {
            return Err("GROWWISE_CORE_EXECUTABLE이 비어 있습니다.".to_string());
        }
        return Ok(Command::new(executable));
    }

    if cfg!(debug_assertions) {
        let python = env::var("GROWWISE_PYTHON").unwrap_or_else(|_| default_python().to_string());
        let mut command = Command::new(python);
        command.args(["-m", "growwise.api.main"]);
        return Ok(command);
    }

    let executable = resource_dir.join("binaries").join(core_binary_name());
    if !executable.is_file() {
        return Err(format!(
            "번들 GrowWise Core 실행 파일을 찾을 수 없습니다: {}",
            executable.display()
        ));
    }
    Ok(Command::new(executable))
}

fn core_binary_name() -> &'static str {
    if cfg!(windows) {
        "growwise-core.exe"
    } else {
        "growwise-core"
    }
}

fn default_python() -> &'static str {
    if cfg!(windows) {
        "python"
    } else {
        "python3"
    }
}

fn read_session_token(path: &PathBuf) -> Result<Option<String>, String> {
    if !path.is_file() {
        return Ok(None);
    }
    let token = fs::read_to_string(path)
        .map_err(|error| format!("GrowWise Core 세션 토큰을 읽을 수 없습니다: {error}"))?;
    let token = token.trim().to_string();
    if token.is_empty() {
        return Ok(None);
    }
    Ok(Some(token))
}

fn core_is_reachable() -> bool {
    let Ok(address) = SocketAddr::from_str(CORE_ADDRESS) else {
        return false;
    };
    TcpStream::connect_timeout(&address, Duration::from_millis(150)).is_ok()
}

fn core_is_authenticated(token: &str) -> bool {
    let Ok(address) = SocketAddr::from_str(CORE_ADDRESS) else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(150)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = [0_u8; 64];
    let Ok(read) = stream.read(&mut response) else {
        return false;
    };
    let prefix = String::from_utf8_lossy(&response[..read]);
    prefix.starts_with("HTTP/1.1 200") || prefix.starts_with("HTTP/1.0 200")
}

#[cfg(test)]
mod tests {
    use super::{core_binary_name, default_python};

    #[test]
    fn platform_names_are_stable() {
        if cfg!(windows) {
            assert_eq!(default_python(), "python");
            assert_eq!(core_binary_name(), "growwise-core.exe");
        } else {
            assert_eq!(default_python(), "python3");
            assert_eq!(core_binary_name(), "growwise-core");
        }
    }
}
