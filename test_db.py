import requests
import json

BASE_URL = "https://riderapp-fzandjczd6gbhfgd.southindia-01.azurewebsites.net/api"


def test_update_status(rider_id, is_online):
    """Test the update_status endpoint"""
    url = f"{BASE_URL}/update_status"

    payload = {
        'rider_id': rider_id,
        'is_online': 1 if is_online else 0
    }

    print(f"Testing update_status with: {payload}")

    try:
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Message: {data.get('message')}")
            if data.get('success'):
                print(f"Updated rider: {data.get('rider_name')}")
        else:
            print(f"Error: {response.status_code}")

    except Exception as e:
        print(f"Request failed: {e}")


def test_get_online_riders():
    """Test the get_online_riders endpoint"""
    url = f"{BASE_URL}/riders/online"

    print(f"\nTesting get_online_riders...")

    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            riders = data.get('riders', [])
            print(f"Number of online riders: {len(riders)}")
            for rider in riders:
                print(f"  - {rider.get('rider_name')} (ID: {rider.get('rider_id')})")
        else:
            print(f"Error: {response.status_code}")

    except Exception as e:
        print(f"Request failed: {e}")


# Run tests
if __name__ == "__main__":
    # Replace with an actual rider ID from your database
    test_rider_id = 1  # Change this to your rider's ID

    # Test setting online
    print("=" * 50)
    print("Test 1: Set rider online")
    print("=" * 50)
    test_update_status(test_rider_id, True)

    print("\n" + "=" * 50)
    print("Test 2: Check online riders")
    print("=" * 50)
    test_get_online_riders()

    print("\n" + "=" * 50)
    print("Test 3: Set rider offline")
    print("=" * 50)
    test_update_status(test_rider_id, False)

    print("\n" + "=" * 50)
    print("Test 4: Check online riders again")
    print("=" * 50)
    test_get_online_riders()