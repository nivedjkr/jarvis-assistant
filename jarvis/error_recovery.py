import asyncio
import functools
import inspect
import time
from typing import Callable, Any, Dict, Optional

class RecoveryStrategy:
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    NOTIFY = "notify"

def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    fallback: Any = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        print(f"[RECOVERY] {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        print(f"[RECOVERY] {func.__name__} failed (attempt {attempt+1}): {e}. Retrying in {current_delay:.1f}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            # All attempts failed
            print(f"[RECOVERY] {func.__name__} failed after {max_attempts} attempts: {last_error}")
            
            if fallback is not None:
                if callable(fallback):
                    return fallback(*args, **kwargs)
                return fallback
            
            return f"Service temporarily unavailable. Error: {str(last_error)[:100]}"
        return wrapper
    return decorator

class ErrorRecovery:
    def __init__(self):
        self.failure_counts: Dict[str, int] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self.CIRCUIT_THRESHOLD = 5
        self.CIRCUIT_RESET_TIME = 300  # 5 minutes

    def is_circuit_open(self, service: str) -> bool:
        if service not in self.circuit_breakers:
            return False
        cb = self.circuit_breakers[service]
        if cb['open']:
            # Check if reset time has passed
            if time.time() - cb['opened_at'] > self.CIRCUIT_RESET_TIME:
                cb['open'] = False
                cb['failures'] = 0
                print(f"[CIRCUIT] {service} reset")
                return False
            return True
        return False

    def record_failure(self, service: str):
        if service not in self.circuit_breakers:
            self.circuit_breakers[service] = {
                'open': False,
                'failures': 0,
                'opened_at': 0
            }
        cb = self.circuit_breakers[service]
        cb['failures'] += 1
        if cb['failures'] >= self.CIRCUIT_THRESHOLD:
            cb['open'] = True
            cb['opened_at'] = time.time()
            print(f"[CIRCUIT] {service} circuit opened after {cb['failures']} failures")

    def record_success(self, service: str):
        if service in self.circuit_breakers:
            self.circuit_breakers[service]['failures'] = 0

    async def call_with_recovery(
        self, service: str, 
        func: Callable,
        fallback_msg: Optional[str] = None,
        *args, **kwargs) -> Any:
        
        if self.is_circuit_open(service):
            return (f"{service} is temporarily unavailable (circuit open). "
                    f"Trying again in a few minutes, sir.")
        
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
            self.record_success(service)
            return result
        except Exception as e:
            self.record_failure(service)
            error_msg = str(e)
            
            # Classify error type
            if '403' in error_msg or 'auth' in error_msg.lower():
                return f"{service} authentication failed. Check API key, sir."
            elif '429' in error_msg or 'rate' in error_msg.lower():
                return f"{service} rate limit hit. Waiting before retry, sir."
            elif 'timeout' in error_msg.lower():
                return f"{service} timed out. Network may be slow, sir."
            elif 'connection' in error_msg.lower():
                return f"{service} unreachable. Check internet connection, sir."
            else:
                return fallback_msg or f"{service} error: {error_msg[:100]}"

# Global instance
recovery = ErrorRecovery()
