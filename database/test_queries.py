from queries import (
    get_departments,
    get_doctors_by_department,
    get_doctor_by_name,
    get_services,
    search_faqs,
)

print("--- Departments ---")
for row in get_departments():
    print(row)

print("\n--- Doctors in cardio ---")
for row in get_doctors_by_department("cardio"):
    print(row)

print("\n--- Doctor named Nair ---")
for row in get_doctor_by_name("Nair"):
    print(row)

print("\n--- Services ---")
for row in get_services():
    print(row)

print("\n--- FAQ search: visiting ---")
for row in search_faqs("visiting"):
    print(row)