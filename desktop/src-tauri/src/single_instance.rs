use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4, TcpListener, TcpStream};
use std::thread;
use std::time::Duration;

use tauri::{AppHandle, Manager, Runtime};

// A small pool avoids making GrowWise depend on one arbitrary loopback port. Existing instances
// are identified by an application-specific handshake, so an unrelated local service occupying a
// candidate port is skipped rather than mistaken for GrowWise.
const SINGLE_INSTANCE_PORTS: [u16; 3] = [27431, 27432, 27433];
const SINGLE_INSTANCE_MAGIC: &[u8] = b"GROWWISE_SINGLE_INSTANCE_V1\n";
const SINGLE_INSTANCE_ACK: &[u8] = b"GROWWISE_SINGLE_INSTANCE_ACK_V1\n";
const SINGLE_INSTANCE_IO_TIMEOUT: Duration = Duration::from_millis(300);

pub fn enforce<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    // Probe before binding so an existing GrowWise instance that had to skip an occupied candidate
    // is still discovered.
    for port in SINGLE_INSTANCE_PORTS {
        if notify_existing(port) {
            return Err("GrowWise가 이미 실행 중입니다.".to_string());
        }
    }

    for port in SINGLE_INSTANCE_PORTS {
        let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
        match TcpListener::bind(address) {
            Ok(listener) => {
                spawn_listener(listener, app.clone());
                return Ok(());
            }
            Err(error) if error.kind() == std::io::ErrorKind::AddrInUse => {
                // Close the simultaneous-start race: another GrowWise process can win the bind
                // after our initial probe but before this attempt.
                if notify_existing(port) {
                    return Err("GrowWise가 이미 실행 중입니다.".to_string());
                }
            }
            Err(_) => continue,
        }
    }

    Err("GrowWise 단일 실행 보호 포트를 확보할 수 없습니다.".to_string())
}

fn spawn_listener<R: Runtime>(listener: TcpListener, app: AppHandle<R>) {
    thread::spawn(move || {
        for incoming in listener.incoming() {
            let Ok(mut stream) = incoming else {
                continue;
            };
            let _ = stream.set_read_timeout(Some(SINGLE_INSTANCE_IO_TIMEOUT));
            let _ = stream.set_write_timeout(Some(SINGLE_INSTANCE_IO_TIMEOUT));

            let mut request = vec![0_u8; SINGLE_INSTANCE_MAGIC.len()];
            if stream.read_exact(&mut request).is_err() || request != SINGLE_INSTANCE_MAGIC {
                continue;
            }

            let _ = stream.write_all(SINGLE_INSTANCE_ACK);
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    });
}

fn notify_existing(port: u16) -> bool {
    let address = SocketAddr::V4(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, SINGLE_INSTANCE_IO_TIMEOUT) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(SINGLE_INSTANCE_IO_TIMEOUT));
    let _ = stream.set_write_timeout(Some(SINGLE_INSTANCE_IO_TIMEOUT));
    if stream.write_all(SINGLE_INSTANCE_MAGIC).is_err() {
        return false;
    }

    let mut response = vec![0_u8; SINGLE_INSTANCE_ACK.len()];
    stream.read_exact(&mut response).is_ok() && response == SINGLE_INSTANCE_ACK
}

#[cfg(test)]
mod tests {
    use super::{notify_existing, SINGLE_INSTANCE_ACK, SINGLE_INSTANCE_MAGIC};
    use std::io::{Read, Write};
    use std::net::{Ipv4Addr, TcpListener};
    use std::thread;

    #[test]
    fn growwise_handshake_identifies_an_existing_instance() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).expect("bind test listener");
        let port = listener.local_addr().expect("listener address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept probe");
            let mut request = vec![0_u8; SINGLE_INSTANCE_MAGIC.len()];
            stream.read_exact(&mut request).expect("read handshake");
            assert_eq!(request, SINGLE_INSTANCE_MAGIC);
            stream
                .write_all(SINGLE_INSTANCE_ACK)
                .expect("write handshake ack");
        });

        assert!(notify_existing(port));
        server.join().expect("join test listener");
    }

    #[test]
    fn unrelated_loopback_service_is_not_treated_as_growwise() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).expect("bind test listener");
        let port = listener.local_addr().expect("listener address").port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept probe");
            let mut request = vec![0_u8; SINGLE_INSTANCE_MAGIC.len()];
            let _ = stream.read_exact(&mut request);
            let _ = stream.write_all(b"NOT_GROWWISE\n");
        });

        assert!(!notify_existing(port));
        server.join().expect("join test listener");
    }
}
