import requests

def check_citybank():
    try:
        res = requests.get('http://localhost:8000/api/datamatrix?limit=500')
        data = res.json()
        found = [s for s in data if s['Symbol'] == 'CITYBANK']
        if found:
            print(f"CITYBANK data: {found[0]}")
        else:
            print("CITYBANK not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_citybank()
