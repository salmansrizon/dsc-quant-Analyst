import requests

def check_keys():
    try:
        res = requests.get('http://localhost:8000/api/datamatrix?limit=1')
        data = res.json()
        if data:
            print(f"Keys: {list(data[0].keys())}")
            print(f"Sample Row: {data[0]}")
        else:
            print("No data in datamatrix")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_keys()
