use std::env;
use std::fs::File;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

const CORE_HOST: &str = "127.0.0.1";
const STARTUP_ATTEMPTS: usize = 100;
const STARTUP_INTERVAL: Duration = Duration::from_millis(100);
const DESKTOP_PROTOCOL_VERSION: u32 = 1;

pub struct CoreProcessManager {
    child: Mutex<Option<Child>>,
    base_url: String,
    session_token: String,
}

impl CoreProcessManager {
    pub fn ensure_started(resource_dir: &Path, data_dir: &Path) -> Result<Self, String> {
        let port = reserve_loopback_port()?;
        let session_token = secure_session_token()?;
        let base_url = format!("http://{CORE_HOST}:{port}");

        let mut command = core_command(resource_dir)?;
        command
            .env("GROWWISE_API_HOST", CORE_HOST)
            .env("GROWWISE_API_PORT", port.to_string())
            .env("GROWWISE_SESSION_TOKEN", &session_token)
            .env("GROWWISE_DATA_DIR", data_dir)
            .stdin(Stdio::null());

        if cfg!(debug_assertions) {
            command.stdout(Stdio::inherit()).stderr(Stdio::inherit());
        } else {
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }

        let mut child = command
            .spawn()
            .map_err(|error| format!("GrowWise Core를 시작할 수 없습니다: {error}"))?;

        for _ in 0..STARTUP_ATTEMPTS {
            if authenticated_handshake(port, &session_token) {
                return Ok(Self {
                    child: Mutex::new(Some(child)),
                    base_url,
                    session_token,
                });
            }

            if let Some(status) = child
                .try_wait()
                .map_err(|error| format!("GrowWise Core 상태 확인 실패: {error}"))?
            {
                return Err(format!(
                    "GrowWise Core가 준비되기 전에 종료되었습니다: {status}"
                ));
            }
            thread::sleep(STARTUP_INTERVAL);
        }

        let _ = child.kill();
        let _ = child.wait();
        Err("GrowWise Core 시작 제한 시간을 초과했습니다.".to_string())
    }

    pub fn started_by_desktop(&self) -> bool {
        self.child
            .lock()
            .map(|child| child.is_some())
            .unwrap_or(false)
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn session_token(&self) -> &str {
        &self.session_token
    }
}

impl Drop for CoreProcessManager {
    fn drop(&mut self) {
        let Ok(child_slot) = self.child.get_mut() else {
            self.session_token.clear();
            return;
        };
        if let Some(child) = child_slot.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *child_slot = None;
        self.session_token.clear();
    }
}

fn core_command(resource_dir: &Path) -> Result<Command, String> {
    if cfg!(debug_assertions) {
        if let Ok(executable) = env::var("GROWWISE_CORE_EXECUTABLE") {
            if executable.trim().is_empty() {
                return Err("GROWWISE_CORE_EXECUTABLE이 비어 있습니다.".to_string());
            }
            return Ok(Command::new(executable));
        }

        let python = env::var("GROWWISE_PYTHON").unwrap_or_else(|_| default_python().to_string());
        let mut command = Command::new(python);
        command.args(["-m", "growwise.api.secure_entry"]);
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

fn reserve_loopback_port() -> Result<u16, String> {
    let listener = TcpListener::bind((CORE_HOST, 0))
        .map_err(|error| format!("GrowWise Core 포트를 예약할 수 없습니다: {error}"))?;
    listener
        .local_addr()
        .map(|address| address.port())
        .map_err(|error| format!("GrowWise Core 포트를 확인할 수 없습니다: {error}"))
}

fn secure_session_token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    fill_secure_random(&mut bytes)?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

#[cfg(unix)]
fn fill_secure_random(bytes: &mut [u8]) -> Result<(), String> {
    File::open("/dev/urandom")
        .and_then(|mut source| source.read_exact(bytes))
        .map_err(|error| format!("OS 난수 생성기를 읽을 수 없습니다: {error}"))
}

#[cfg(windows)]
fn fill_secure_random(bytes: &mut [u8]) -> Result<(), String> {
    use std::ffi::c_void;

    #[link(name = "bcrypt")]
    extern "system" {
        #[link_name = "BCryptGenRandom"]
        fn bcrypt_gen_random(
            algorithm: *mut c_void,
            buffer: *mut u8,
            buffer_len: u32,
            flags: u32,
        ) -> i32;
    }

    const BCRYPT_USE_SYSTEM_PREFERRED_RNG: u32 = 0x0000_0002;
    // SAFETY: BCryptGenRandom is called with the system-preferred RNG, a valid writable buffer,
    // and its exact byte length. The API does not retain the pointer after returning.
    let status = unsafe {
        bcrypt_gen_random(
            std::ptr::null_mut(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    };
    if status == 0 {
        Ok(())
    } else {
        Err(format!("Windows CSPRNG failed with NTSTATUS {status:#x}"))
    }
}

fn authenticated_handshake(port: u16, session_token: &str) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(180)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(300)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));
    let request = format!(
        "GET /_desktop/handshake HTTP/1.1\r\nHost: {CORE_HOST}:{port}\r\n\
         Authorization: Bearer {session_token}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    let ok_status = response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200");
    let expected_protocol = format!("\"protocol_version\":{DESKTOP_PROTOCOL_VERSION}");
    ok_status
        && response.contains("\"product\":\"growwise-core\"")
        && response.contains(&expected_protocol)
}

#[cfg(test)]
mod tests {
    use super::{core_binary_name, default_python, reserve_loopback_port, secure_session_token};

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

    #[test]
    fn desktop_session_uses_ephemeral_port_and_strong_token() {
        let port = reserve_loopback_port().expect("ephemeral port");
        assert_ne!(port, 0);
        let first = secure_session_token().expect("session token");
        let second = secure_session_token().expect("session token");
        assert_eq!(first.len(), 64);
        assert_eq!(second.len(), 64);
        assert_ne!(first, second);
    }
}
