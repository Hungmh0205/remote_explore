import psutil
try:
    count = 0
    print("Starting service scan...")
    for svc in psutil.win_service_iter():
        count += 1
        if count <= 5:
            try:
                print(f"Service: {svc.name()} - {svc.display_name()}")
            except Exception as e:
                print(f"Service (Error getting details): {e}")
    print(f"Total services found: {count}")
except Exception as e:
    print(f"FATAL ERROR: {e}")
