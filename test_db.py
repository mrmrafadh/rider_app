import requests
import json
import time

BASE_URL = "https://riderapp-fzandjczd6gbhfgd.southindia-01.azurewebsites.net/api"


def debug_test():
    print("🔍 DEBUG TEST FOR RIDER SYSTEM")
    print("=" * 60)

    # Step 1: Test login
    print("\n1. LOGIN TEST")
    print("-" * 40)

    login_data = {
        'rider_name': 'rafath',
        'password': 'rafath'
    }

    try:
        response = requests.post(f"{BASE_URL}/login", json=login_data, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            login_result = response.json()
            print(f"Response: {json.dumps(login_result, indent=2)}")

            if login_result['success']:
                rider_id = login_result['rider_id']
                print(f"✅ Login successful! Rider ID: {rider_id}")

                # Step 2: Go online
                print("\n2. GO ONLINE TEST")
                print("-" * 40)

                status_data = {
                    'rider_id': rider_id,
                    'is_online': 1
                }

                response2 = requests.post(f"{BASE_URL}/update_status", json=status_data, timeout=10)
                print(f"Status: {response2.status_code}")
                print(f"Response: {json.dumps(response2.json(), indent=2)}")

                time.sleep(2)  # Wait for update

                # Step 3: Update location
                print("\n3. UPDATE LOCATION TEST")
                print("-" * 40)

                location_data = {
                    'rider_id': rider_id,
                    'latitude': 12.9716,
                    'longitude': 77.5946
                }

                response3 = requests.post(f"{BASE_URL}/update_location", json=location_data, timeout=10)
                print(f"Status: {response3.status_code}")
                print(f"Response: {json.dumps(response3.json(), indent=2)}")

                time.sleep(2)

                # Step 4: Check online riders
                print("\n4. CHECK ONLINE RIDERS")
                print("-" * 40)

                response4 = requests.get(f"{BASE_URL}/riders/online", timeout=10)
                print(f"Status: {response4.status_code}")
                online_result = response4.json()
                print(f"Response: {json.dumps(online_result, indent=2)}")

                if online_result['success']:
                    print(f"\n📊 ANALYSIS:")
                    print(f"   Total online riders reported: {online_result['count']}")

                    if online_result['riders']:
                        print("\n   👥 Online Riders Found:")
                        for rider in online_result['riders']:
                            print(f"   - {rider['rider_name']} (ID: {rider['rider_id']})")
                            print(f"     Online: {rider['is_online']}")
                            print(f"     Location: {rider.get('latitude', 'N/A')}, {rider.get('longitude', 'N/A')}")
                    else:
                        print("\n   ❌ PROBLEM: No riders in 'riders' array!")
                        print("   Possible causes:")
                        print("   1. rider_status table doesn't have is_online=TRUE")
                        print("   2. JOIN query is filtering out the rider")
                        print("   3. Database commit issue")

                        # Step 5: Direct database check
                        print("\n5. DIRECT DATABASE CHECK")
                        print("-" * 40)
                        print("Checking what's actually in the database...")

                        # Try to get the rider's status directly
                        direct_status_url = f"{BASE_URL}/rider/{rider_id}/location"
                        response5 = requests.get(direct_status_url, timeout=10)
                        print(f"Direct location check: Status {response5.status_code}")
                        if response5.status_code == 200:
                            print(f"Response: {json.dumps(response5.json(), indent=2)}")
                        else:
                            print(f"Response: {response5.text}")

                # Step 6: Go offline
                print("\n6. GO OFFLINE TEST")
                print("-" * 40)

                offline_data = {
                    'rider_id': rider_id,
                    'is_online': 0
                }

                response6 = requests.post(f"{BASE_URL}/update_status", json=offline_data, timeout=10)
                print(f"Status: {response6.status_code}")
                print(f"Response: {json.dumps(response6.json(), indent=2)}")

            else:
                print(f"❌ Login failed: {login_result['message']}")
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


def check_database_state():
    """Check what's actually in the database"""
    print("\n🔍 DATABASE STATE CHECK")
    print("=" * 60)

    # First get online riders
    print("\n1. Current online riders from API:")
    response = requests.get(f"{BASE_URL}/riders/online", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(data, indent=2)}")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")

    # Try to login with different riders to see what's in DB
    print("\n2. Checking available riders:")
    test_users = [
        {'name': 'rafath', 'password': 'rafath'},
        {'name': 'hamdi', 'password': 'hamdi'},
    ]

    for user in test_users:
        try:
            response = requests.post(f"{BASE_URL}/login",
                                     json={'rider_name': user['name'], 'password': user['password']},
                                     timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"   ✅ {user['name']}: Can login (ID: {data.get('rider_id')})")

                    # Check their status
                    rider_id = data.get('rider_id')
                    status_response = requests.post(f"{BASE_URL}/update_status",
                                                    json={'rider_id': rider_id, 'is_online': 0},
                                                    timeout=5)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"      Current status: {status_data.get('is_online')}")
                else:
                    print(f"   ❌ {user['name']}: Login failed - {data.get('message')}")
            else:
                print(f"   ❌ {user['name']}: HTTP error {response.status_code}")
        except:
            print(f"   ⚠️  {user['name']}: Connection failed")


if __name__ == "__main__":
    debug_test()
    check_database_state()