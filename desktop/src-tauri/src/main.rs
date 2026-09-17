use std::io;

#[cfg(unix)]
use std::fs::{File, OpenOptions};
#[cfg(unix)]
use std::os::fd::AsRawFd;
#[cfg(unix)]
use std::os::raw::c_int;
#[cfg(unix)]
use std::path::PathBuf;

#[cfg(windows)]
use std::ffi::c_void;

#[cfg(unix)]
struct DesktopInstanceGuard {
    _file: File,
}

#[cfg(windows)]
struct DesktopInstanceGuard {
    handle: *mut c_void,
}

#[cfg(windows)]
impl Drop for DesktopInstanceGuard {
    fn drop(&mut self) {
        unsafe {
            close_handle(self.handle);
        }
    }
}

#[cfg(unix)]
fn acquire_instance_guard() -> io::Result<DesktopInstanceGuard> {
    const LOCK_EX: c_int = 2;
    const LOCK_NB: c_int = 4;

    let lock_path = std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join(".growwise-desktop.lock");
    let file = OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(lock_path)?;
    let result = unsafe { flock(file.as_raw_fd(), LOCK_EX | LOCK_NB) };
    if result != 0 {
        let error = io::Error::last_os_error();
        if error.kind() == io::ErrorKind::WouldBlock {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "GrowWise Desktop is already running",
            ));
        }
        return Err(error);
    }
    Ok(DesktopInstanceGuard { _file: file })
}

#[cfg(windows)]
fn acquire_instance_guard() -> io::Result<DesktopInstanceGuard> {
    const ERROR_ALREADY_EXISTS: u32 = 183;
    let name: Vec<u16> = "Local\\io.github.jdeun.growwise.desktop"
        .encode_utf16()
        .chain(std::iter::once(0))
        .collect();
    let handle = unsafe { create_mutex_w(std::ptr::null_mut(), 0, name.as_ptr()) };
    if handle.is_null() {
        return Err(io::Error::last_os_error());
    }
    if unsafe { get_last_error() } == ERROR_ALREADY_EXISTS {
        unsafe {
            close_handle(handle);
        }
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "GrowWise Desktop is already running",
        ));
    }
    Ok(DesktopInstanceGuard { handle })
}

#[cfg(unix)]
extern "C" {
    fn flock(fd: c_int, operation: c_int) -> c_int;
}

#[cfg(windows)]
#[link(name = "kernel32")]
extern "system" {
    #[link_name = "CreateMutexW"]
    fn create_mutex_w(
        lp_mutex_attributes: *mut c_void,
        initial_owner: i32,
        name: *const u16,
    ) -> *mut c_void;
    #[link_name = "GetLastError"]
    fn get_last_error() -> u32;
    #[link_name = "CloseHandle"]
    fn close_handle(object: *mut c_void) -> i32;
}

fn main() {
    let _instance_guard = match acquire_instance_guard() {
        Ok(guard) => guard,
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            eprintln!("{error}");
            return;
        }
        Err(error) => {
            eprintln!("failed to acquire GrowWise Desktop instance lock: {error}");
            std::process::exit(1);
        }
    };
    growwise_desktop_lib::run();
}
