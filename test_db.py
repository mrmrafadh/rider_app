import requests
import json
import time
import random
from datetime import datetime

BASE_URL = "https://riderapp-fzandjczd6gbhfgd.southindia-01.azurewebsites.net/api"


class RiderSystemTester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.test_rider_id = None
        self.session = requests.Session()

    def print_header(self, title):
        """Print formatted header"""
        print("\n" + "=" * 60)
        print(f"🚀 {title}")
        print("=" * 60)

    def print_section(self, title):
        """Print section header"""
        print(f"\n📋 {title}")
        print("-" * 40)

    def test_database_health(self):
        """Test database connection and basic queries"""
        self.print_header("DATABASE HEALTH CHECK")

        try:
            # Test if API is reachable
            response = self.session.get(f"{self.base_url}/riders/online", timeout=5)
            print(f"✅ API is reachable (Status: {response.status_code})")

            # Try to get rider count
            response = self.session.get(f"{self.base_url}/riders", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Database connection successful")
                if 'riders' in data:
                    print(f"📊 Total riders in database: {len(data['riders'])}")
                return True
            else:
                print(f"⚠️  Could not fetch riders (Status: {response.status_code})")
                return False

        except Exception as e:
            print(f"❌ Database health check failed: {e}")
            return False

    def test_login(self, rider_name="test_rider", password="password123"):
        """Test rider login with the given schema"""
        self.print_section("TEST RIDER LOGIN")

        url = f"{self.base_url}/login"
        payload = {
            'rider_name': rider_name,
            'password': password
        }

        try:
            response = self.session.post(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=10
            )

            print(f"📤 Request: POST {url}")
            print(f"📦 Payload: {json.dumps(payload, indent=2)}")
            print(f"📥 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"📄 Response: {json.dumps(data, indent=2)}")

                if data.get('success'):
                    print(f"\n✅ LOGIN SUCCESSFUL!")
                    print(f"   👤 Rider ID: {data.get('rider_id')}")
                    print(f"   📛 Rider Name: {data.get('rider_name')}")
                    self.test_rider_id = data.get('rider_id')
                    return data
                else:
                    print(f"\n❌ LOGIN FAILED: {data.get('message')}")
                    return None
            else:
                print(f"\n❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return None

    def test_update_status(self, rider_id, is_online):
        """Test updating rider online status (rider_status table)"""
        self.print_section(f"UPDATE STATUS - {'ONLINE' if is_online else 'OFFLINE'}")

        url = f"{self.base_url}/update_status"
        payload = {
            'rider_id': rider_id,
            'is_online': 1 if is_online else 0
        }

        print(f"📤 Request: POST {url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        print(f"📚 Expected DB Action: Update rider_status table")

        try:
            response = self.session.post(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=10
            )

            print(f"📥 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"📄 Response: {json.dumps(data, indent=2)}")

                if data.get('success'):
                    print(f"\n✅ STATUS UPDATE SUCCESSFUL!")
                    print(f"   📝 Message: {data.get('message')}")
                    print(f"   🔄 Is Online: {data.get('is_online')}")
                    print(f"   🆔 Rider ID: {data.get('rider_id')}")

                    # Verify the status in the response matches what we sent
                    expected_status = bool(is_online)
                    actual_status = data.get('is_online', False)

                    if expected_status == actual_status:
                        print(f"   ✅ Status verified: {actual_status}")
                    else:
                        print(f"   ⚠️  Status mismatch! Expected: {expected_status}, Got: {actual_status}")

                    return True
                else:
                    print(f"\n❌ STATUS UPDATE FAILED: {data.get('message')}")
                    return False
            else:
                print(f"\n❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return False

    def test_update_location(self, rider_id, latitude=None, longitude=None):
        """Test updating rider location (rider_location table)"""
        self.print_section("UPDATE LOCATION")

        url = f"{self.base_url}/update_location"

        # Use random location if not provided (Bangalore coordinates)
        if latitude is None:
            latitude = 12.9716 + random.uniform(-0.01, 0.01)
        if longitude is None:
            longitude = 77.5946 + random.uniform(-0.01, 0.01)

        payload = {
            'rider_id': rider_id,
            'latitude': round(latitude, 7),
            'longitude': round(longitude, 7)
        }

        print(f"📤 Request: POST {url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        print(f"📚 Expected DB Action: Insert into rider_location table")

        try:
            response = self.session.post(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=10
            )

            print(f"📥 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"📄 Response: {json.dumps(data, indent=2)}")

                if data.get('success'):
                    print(f"\n✅ LOCATION UPDATE SUCCESSFUL!")
                    print(f"   📍 Latitude: {payload['latitude']}")
                    print(f"   📍 Longitude: {payload['longitude']}")
                    print(f"   📝 Message: {data.get('message')}")
                    return True
                else:
                    print(f"\n❌ LOCATION UPDATE FAILED: {data.get('message')}")
                    return False
            else:
                print(f"\n❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return False

    def test_get_online_riders(self):
        """Test getting online riders with location data"""
        self.print_section("GET ONLINE RIDERS")

        url = f"{self.base_url}/riders/online"

        print(f"📤 Request: GET {url}")
        print(f"📚 Expected SQL Query:")
        print(f"""   SELECT r.rider_id, r.rider_name, rs.is_online, 
                rl.latitude, rl.longitude, rl.location_time
        FROM riders r
        JOIN rider_status rs ON r.rider_id = rs.rider_id
        LEFT JOIN rider_location rl ON r.rider_id = rl.rider_id
        WHERE rs.is_online = TRUE
        ORDER BY rl.location_time DESC""")

        try:
            response = self.session.get(url, timeout=10)
            print(f"📥 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"📄 Response: {json.dumps(data, indent=2)}")

                if data.get('success'):
                    riders = data.get('riders', [])
                    count = data.get('count', len(riders))

                    print(f"\n✅ ONLINE RIDERS FETCHED SUCCESSFULLY!")
                    print(f"   📊 Total Online Riders: {count}")

                    if riders:
                        print(f"\n   👥 Online Riders List:")
                        for i, rider in enumerate(riders, 1):
                            print(f"\n   {i}. Rider ID: {rider.get('rider_id')}")
                            print(f"      Name: {rider.get('rider_name')}")
                            print(f"      Online: {rider.get('is_online')}")
                            print(f"      Location: {rider.get('latitude', 'N/A')}, {rider.get('longitude', 'N/A')}")
                            print(f"      Last Updated: {rider.get('last_updated', rider.get('location_time', 'N/A'))}")
                    else:
                        print(f"\n   📭 No riders are currently online")

                    return True
                else:
                    print(f"\n❌ FAILED TO FETCH ONLINE RIDERS: {data.get('message')}")
                    return False
            else:
                print(f"\n❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"\n❌ Request failed: {e}")
            return False

    def test_full_workflow(self, rider_name="test_rider", password="password123"):
        """Test complete rider workflow"""
        self.print_header("COMPLETE RIDER WORKFLOW TEST")

        results = {
            'login': False,
            'go_online': False,
            'update_location': False,
            'get_online_riders': False,
            'go_offline': False,
            'final_check': False
        }

        print("🔍 Testing complete workflow for rider system...")
        print(f"📅 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Step 1: Database health check
        print("\n1️⃣  STEP 1: Database Health Check")
        results['health_check'] = self.test_database_health()
        if not results['health_check']:
            print("❌ Cannot proceed - database health check failed")
            return results

        # Step 2: Login
        print("\n2️⃣  STEP 2: Rider Login")
        login_data = self.test_login(rider_name, password)
        results['login'] = login_data is not None

        if not results['login']:
            print("❌ Cannot proceed - login failed")
            return results

        rider_id = self.test_rider_id
        print(f"✅ Using Rider ID: {rider_id}")

        # Wait a moment
        time.sleep(1)

        # Step 3: Go Online
        print("\n3️⃣  STEP 3: Go Online")
        results['go_online'] = self.test_update_status(rider_id, True)

        if results['go_online']:
            print("✅ Rider is now online")
        else:
            print("❌ Failed to go online")

        # Wait for status to propagate
        time.sleep(2)

        # Step 4: Update Location
        print("\n4️⃣  STEP 4: Update Location")
        results['update_location'] = self.test_update_location(rider_id)

        # Wait a moment
        time.sleep(1)

        # Step 5: Get Online Riders (should include our rider)
        print("\n5️⃣  STEP 5: Check Online Riders")
        results['get_online_riders'] = self.test_get_online_riders()

        # Step 6: Update location again (simulate movement)
        print("\n6️⃣  STEP 6: Update Location Again (Movement)")
        self.test_update_location(rider_id)

        # Wait a moment
        time.sleep(1)

        # Step 7: Go Offline
        print("\n7️⃣  STEP 7: Go Offline")
        results['go_offline'] = self.test_update_status(rider_id, False)

        # Wait for status to propagate
        time.sleep(2)

        # Step 8: Final check - should be no online riders
        print("\n8️⃣  STEP 8: Final Check (Should be no online riders)")
        results['final_check'] = self.test_get_online_riders()

        # Summary
        self.print_header("TEST SUMMARY")
        print("📊 Test Results:")
        for step, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {step.replace('_', ' ').title():20} {status}")

        passed = sum(results.values())
        total = len(results)
        print(f"\n🎯 Score: {passed}/{total} ({passed / total * 100:.1f}%)")

        if passed == total:
            print("\n🏆 ALL TESTS PASSED! System is working correctly.")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Check the logs above.")

        return results

    def test_specific_scenarios(self):
        """Test specific edge cases and scenarios"""
        self.print_header("SPECIAL SCENARIO TESTS")

        scenarios = []

        # Scenario 1: Invalid rider ID
        print("\n🔍 Scenario 1: Invalid Rider ID")
        result = self.test_update_status(999999, True)  # Non-existent rider
        scenarios.append(("Invalid Rider ID", not result))  # Should fail

        # Scenario 2: Multiple location updates
        print("\n🔍 Scenario 2: Multiple Rapid Location Updates")
        if self.test_rider_id:
            success_count = 0
            for i in range(3):
                print(f"   Update {i + 1}:")
                if self.test_update_location(self.test_rider_id):
                    success_count += 1
                time.sleep(0.5)
            scenarios.append(("Multiple Location Updates", success_count == 3))

        # Scenario 3: Rapid status toggling
        print("\n🔍 Scenario 3: Rapid Status Toggling")
        if self.test_rider_id:
            toggles = [True, False, True, False]
            success_count = 0
            for status in toggles:
                if self.test_update_status(self.test_rider_id, status):
                    success_count += 1
                time.sleep(0.5)
            scenarios.append(("Rapid Status Toggles", success_count == len(toggles)))

        # Print scenario results
        print("\n📊 Scenario Results:")
        for scenario, result in scenarios:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {scenario:25} {status}")


def main():
    """Main test runner"""
    print("🚴‍♂️ RIDER MANAGEMENT SYSTEM TEST SUITE")
    print("=" * 60)

    # Create tester instance
    tester = RiderSystemTester(BASE_URL)

    # You can customize test credentials here
    TEST_CREDENTIALS = [
        {"rider_name": "rafath", "password": "rafath"},
        {"rider_name": "hamdi", "password": "hamdi"},
    ]

    # Run complete workflow test
    print("\n" + "=" * 60)
    print("🏃‍♂️ STARTING COMPLETE WORKFLOW TEST")
    print("=" * 60)

    # Test with first set of credentials
    credentials = TEST_CREDENTIALS[0]
    results = tester.test_full_workflow(
        rider_name=credentials['rider_name'],
        password=credentials['password']
    )

    # Run special scenarios
    tester.test_specific_scenarios()

    # Quick test of other endpoints if they exist
    print("\n" + "=" * 60)
    print("🔧 ADDITIONAL ENDPOINT TESTS")
    print("=" * 60)

    # Test other potential endpoints
    endpoints_to_test = [
        "/api/login",
        "/api/update_status",
        "/api/update_location",
        "/api/riders/online",
        "/api/riders/all",  # If exists
        "/api/stats",  # If exists
    ]

    for endpoint in endpoints_to_test:
        try:
            url = f"{BASE_URL}{endpoint.replace('/api', '')}"
            response = tester.session.get(url, timeout=5)
            print(f"{'✅' if response.status_code < 400 else '❌'} {endpoint:25} Status: {response.status_code}")
        except:
            print(f"❌ {endpoint:25} Failed to connect")

    print("\n" + "=" * 60)
    print("🎉 TEST SUITE COMPLETE")
    print("=" * 60)
    print(f"📅 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()