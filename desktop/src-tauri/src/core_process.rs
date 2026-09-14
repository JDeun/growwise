use std::env;
use std::net::{SocketAddr, TcpStream};
use std::process::{Child, Command, Stdio};
use std::str::FromStr;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

const CORE_ADDRESS: &str = "127.0.0.1:8765";
const STARTUP_ATTEMPTS: usize = 80;
const STARTUP_INTERVAL: Duration = Duration::from_millis(100);

pub struct CoreProcessManager {
    child: Mutex<Option<Child>>,
}

impl CoreProcessManager {
    pub fn ensure_started() -> Result<Self, String> {
        if core_is_reachable() {
            return Ok(Self {
                child: Mutex::new(None),
            });
        }

        let mut command = core_command()?;
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
            if core_is_reachable() {
                return Ok(Self {
                    child: Mutex::new(Some(child)),
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
    }
}

fn core_command() -> Result<Command, String> {
    if let Ok(executable) = env::var("GROWWISE_CORE_EXECUTABLE") {
        if executable.trim().is_empty() {
            return Err("GROWWISE_CORE_EXECUTABLE이 비어 있습니다.".to_string());
        }
        return Ok(Command::new(executable));
    }

    if !cfg!(debug_assertions) {
        return Err(
            "배포 빌드에는 GROWWISE_CORE_EXECUTABLE로 번들 Core 실행 파일을 지정해야 합니다."
                .to_string(),
        );
    }

    let python = env::var("GROWWISE_PYTHON").unwrap_or_else(|_| default_python().to_string());
    let mut command = Command::new(python);
    command.args(["-m", "growwise.api.main"]);
    Ok(command)
}

fn default_python() -> &'static str {
    if cfg!(windows) {
        "python"
    } else {
        "python3"
    }
}

fn core_is_reachable() -> bool {
    let Ok(address) = SocketAddr::from_str(CORE_ADDRESS) else {
        return false;
    };
    TcpStream::connect_timeout(&address, Duration::from_millis(150)).is_ok()
}

#[cfg(test)]
mod tests {
    use super::default_python;

    #[test]
    fn default_python_is_platform_specific() {
        if cfg!(windows) {
            assert_eq!(default_python(), "python");
        } else {
            assert_eq!(default_python(), "python3");
        }
    }
}
