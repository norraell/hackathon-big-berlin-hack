"""Generate mock data for insurants, policies, and claims."""

import asyncio
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_async_session, init_db
from app.claims.insurant_models import (
    Insurant,
    Policy,
    ClaimsHistory,
    VehicleUseType,
    PolicyStatus,
)


async def generate_mock_data():
    """Generate comprehensive mock data for testing."""
    
    print("Initializing database...")
    await init_db()
    
    async with get_async_session() as session:
        print("Generating mock insurants...")
        
        # Insurant 1: Max Mustermann (Active policy with Vollkasko)
        insurant1_id = str(uuid4())
        insurant1 = Insurant(
            insurant_id=insurant1_id,
            first_name="Max",
            last_name="Mustermann",
            date_of_birth=date(1985, 3, 15),
            email="max.mustermann@example.de",
            phone="+49 30 12345678",
            address_street="Hauptstraße 123",
            address_city="Berlin",
            address_postal_code="10115",
            address_country="DE",
            preferred_language="de",
            preferred_communication_channel="email",
            has_power_of_attorney=False,
            is_vulnerable_customer=False,
            marketing_consent=True,
            customer_since=date(2020, 1, 15),
            metadata={
                "customer_segment": "premium",
                "nps_score": 9,
            }
        )
        session.add(insurant1)
        
        # Policy 1: Max's BMW with Vollkasko
        policy1 = Policy(
            policy_id=str(uuid4()),
            policy_number="POL-2024-001234",
            insurant_id=insurant1_id,
            product_name="KFZ Komfort Plus",
            tariff_version="2024.1",
            effective_date=date(2024, 1, 1),
            renewal_date=date(2025, 1, 1),
            status=PolicyStatus.ACTIVE.value,
            annual_premium=1850.00,
            payment_status="current",
            license_plate="B-MW-1234",
            vin="WBADT43452G123456",
            vehicle_make="BMW",
            vehicle_model="3er 320d",
            first_registration=date(2022, 6, 15),
            engine_power_kw=140,
            fuel_type="Diesel",
            vehicle_value=42000.00,
            current_sum_insured=42000.00,
            use_type=VehicleUseType.PRIVATE.value,
            annual_mileage=15000,
            garage_address="Hauptstraße 123, 10115 Berlin",
            liability_sum=100000000.0,
            has_vollkasko=True,
            has_teilkasko=True,
            deductible_vollkasko=500.0,
            deductible_teilkasko=150.0,
            addons={
                "gap_coverage": True,
                "neuwert_period_months": 24,
                "mallorca_police": True,
                "auslandsschadenschutz": True,
                "schutzbrief": True,
                "fahrerschutz": True,
            },
            sf_class_liability="SF10",
            sf_class_vollkasko="SF5",
            has_rabattschutz=True,
            has_werkstattbindung=False,
            driver_scope="named_drivers",
            min_driver_age=23,
            named_drivers=[
                {
                    "name": "Max Mustermann",
                    "date_of_birth": "1985-03-15",
                    "license_since": "2003-04-01",
                    "relationship": "policyholder"
                },
                {
                    "name": "Anna Mustermann",
                    "date_of_birth": "1987-07-22",
                    "license_since": "2005-08-15",
                    "relationship": "spouse"
                }
            ],
            country_coverage=["DE", "AT", "CH", "FR", "IT", "NL", "BE", "PL", "CZ"],
            seasonal_months=None,
            gross_negligence_waived=True,
            has_telematics=False,
            broker_id="BRK-12345",
            metadata={
                "underwriter": "Allianz Deutschland AG",
                "distribution_channel": "broker",
                "last_inspection_date": "2024-03-15",
            }
        )
        session.add(policy1)
        
        # Insurant 2: Anna Schmidt (Active policy with Teilkasko only)
        insurant2_id = str(uuid4())
        insurant2 = Insurant(
            insurant_id=insurant2_id,
            first_name="Anna",
            last_name="Schmidt",
            date_of_birth=date(1992, 8, 20),
            email="anna.schmidt@example.de",
            phone="+49 89 98765432",
            address_street="Leopoldstraße 45",
            address_city="München",
            address_postal_code="80802",
            address_country="DE",
            preferred_language="de",
            preferred_communication_channel="phone",
            has_power_of_attorney=False,
            is_vulnerable_customer=False,
            marketing_consent=False,
            customer_since=date(2022, 6, 1),
            metadata={
                "customer_segment": "standard",
                "nps_score": 7,
            }
        )
        session.add(insurant2)
        
        # Policy 2: Anna's VW Golf with Teilkasko
        policy2 = Policy(
            policy_id=str(uuid4()),
            policy_number="POL-2024-005678",
            insurant_id=insurant2_id,
            product_name="KFZ Basis",
            tariff_version="2024.1",
            effective_date=date(2024, 6, 1),
            renewal_date=date(2025, 6, 1),
            status=PolicyStatus.ACTIVE.value,
            annual_premium=680.00,
            payment_status="current",
            license_plate="M-AS-9876",
            vin="WVWZZZ1KZBW123789",
            vehicle_make="Volkswagen",
            vehicle_model="Golf 1.5 TSI",
            first_registration=date(2020, 3, 10),
            engine_power_kw=96,
            fuel_type="Benzin",
            vehicle_value=18500.00,
            current_sum_insured=18500.00,
            use_type=VehicleUseType.PRIVATE.value,
            annual_mileage=12000,
            garage_address="Leopoldstraße 45, 80802 München",
            liability_sum=100000000.0,
            has_vollkasko=False,
            has_teilkasko=True,
            deductible_vollkasko=None,
            deductible_teilkasko=150.0,
            addons={
                "schutzbrief": True,
            },
            sf_class_liability="SF3",
            sf_class_vollkasko=None,
            has_rabattschutz=False,
            has_werkstattbindung=True,
            driver_scope="policyholder_only",
            min_driver_age=None,
            named_drivers=[
                {
                    "name": "Anna Schmidt",
                    "date_of_birth": "1992-08-20",
                    "license_since": "2010-09-01",
                    "relationship": "policyholder"
                }
            ],
            country_coverage=["DE", "AT", "CH"],
            seasonal_months=None,
            gross_negligence_waived=False,
            has_telematics=False,
            broker_id=None,
            metadata={
                "underwriter": "HUK-COBURG",
                "distribution_channel": "direct",
            }
        )
        session.add(policy2)
        
        # Insurant 3: Thomas Weber (Policy with claims history)
        insurant3_id = str(uuid4())
        insurant3 = Insurant(
            insurant_id=insurant3_id,
            first_name="Thomas",
            last_name="Weber",
            date_of_birth=date(1978, 11, 5),
            email="thomas.weber@example.de",
            phone="+49 40 55566677",
            address_street="Reeperbahn 88",
            address_city="Hamburg",
            address_postal_code="20359",
            address_country="DE",
            preferred_language="de",
            preferred_communication_channel="email",
            has_power_of_attorney=False,
            is_vulnerable_customer=False,
            marketing_consent=True,
            customer_since=date(2018, 3, 1),
            metadata={
                "customer_segment": "standard",
                "nps_score": 6,
            }
        )
        session.add(insurant3)
        
        # Policy 3: Thomas's Mercedes with claims history
        policy3_id = str(uuid4())
        policy3 = Policy(
            policy_id=policy3_id,
            policy_number="POL-2023-009876",
            insurant_id=insurant3_id,
            product_name="KFZ Komfort",
            tariff_version="2023.2",
            effective_date=date(2023, 3, 1),
            renewal_date=date(2025, 3, 1),
            status=PolicyStatus.ACTIVE.value,
            annual_premium=2100.00,
            payment_status="current",
            license_plate="HH-TW-5555",
            vin="WDD2050071F234567",
            vehicle_make="Mercedes-Benz",
            vehicle_model="C-Klasse C200",
            first_registration=date(2021, 1, 20),
            engine_power_kw=150,
            fuel_type="Benzin",
            vehicle_value=38000.00,
            current_sum_insured=38000.00,
            use_type=VehicleUseType.PRIVATE.value,
            annual_mileage=18000,
            garage_address="Reeperbahn 88, 20359 Hamburg",
            liability_sum=100000000.0,
            has_vollkasko=True,
            has_teilkasko=True,
            deductible_vollkasko=500.0,
            deductible_teilkasko=150.0,
            addons={
                "neuwert_period_months": 12,
                "schutzbrief": True,
            },
            sf_class_liability="SF7",
            sf_class_vollkasko="SF3",
            has_rabattschutz=False,
            has_werkstattbindung=False,
            driver_scope="named_drivers",
            min_driver_age=25,
            named_drivers=[
                {
                    "name": "Thomas Weber",
                    "date_of_birth": "1978-11-05",
                    "license_since": "1996-12-01",
                    "relationship": "policyholder"
                }
            ],
            country_coverage=["DE", "AT", "CH", "FR", "IT"],
            seasonal_months=None,
            gross_negligence_waived=True,
            has_telematics=False,
            broker_id="BRK-67890",
            metadata={
                "underwriter": "ERGO Versicherung AG",
                "distribution_channel": "broker",
            }
        )
        session.add(policy3)
        
        # Add claims history for Thomas
        claim_history_1 = ClaimsHistory(
            history_id=str(uuid4()),
            policy_id=policy3_id,
            claim_id=None,
            claim_date=date(2023, 7, 15),
            claim_type="parking_damage",
            claim_amount=1200.00,
            fault_quota=0.0,
            settlement_status="closed",
            fraud_flag=False,
            siu_referral=False,
            coverage_denied=False,
        )
        session.add(claim_history_1)
        
        claim_history_2 = ClaimsHistory(
            history_id=str(uuid4()),
            policy_id=policy3_id,
            claim_id=None,
            claim_date=date(2024, 2, 10),
            claim_type="wildlife_collision",
            claim_amount=3500.00,
            fault_quota=0.0,
            settlement_status="closed",
            fraud_flag=False,
            siu_referral=False,
            coverage_denied=False,
        )
        session.add(claim_history_2)
        
        # Insurant 4: Maria Gonzalez (Seasonal policy)
        insurant4_id = str(uuid4())
        insurant4 = Insurant(
            insurant_id=insurant4_id,
            first_name="Maria",
            last_name="Gonzalez",
            date_of_birth=date(1995, 5, 12),
            email="maria.gonzalez@example.de",
            phone="+49 711 44455566",
            address_street="Königstraße 12",
            address_city="Stuttgart",
            address_postal_code="70173",
            address_country="DE",
            preferred_language="de",
            preferred_communication_channel="email",
            has_power_of_attorney=False,
            is_vulnerable_customer=False,
            marketing_consent=True,
            customer_since=date(2023, 4, 1),
            metadata={
                "customer_segment": "young_driver",
                "nps_score": 8,
            }
        )
        session.add(insurant4)
        
        # Policy 4: Maria's motorcycle with seasonal coverage
        policy4 = Policy(
            policy_id=str(uuid4()),
            policy_number="POL-2024-011223",
            insurant_id=insurant4_id,
            product_name="Motorrad Basis",
            tariff_version="2024.1",
            effective_date=date(2024, 4, 1),
            renewal_date=date(2024, 10, 31),
            status=PolicyStatus.ACTIVE.value,
            annual_premium=450.00,
            payment_status="current",
            license_plate="S-MG-777",
            vin="VBKMZ1234567890AB",
            vehicle_make="Yamaha",
            vehicle_model="MT-07",
            first_registration=date(2023, 5, 1),
            engine_power_kw=54,
            fuel_type="Benzin",
            vehicle_value=7500.00,
            current_sum_insured=7500.00,
            use_type=VehicleUseType.PRIVATE.value,
            annual_mileage=5000,
            garage_address="Königstraße 12, 70173 Stuttgart",
            liability_sum=100000000.0,
            has_vollkasko=False,
            has_teilkasko=True,
            deductible_vollkasko=None,
            deductible_teilkasko=150.0,
            addons={
                "schutzbrief": True,
            },
            sf_class_liability="SF1",
            sf_class_vollkasko=None,
            has_rabattschutz=False,
            has_werkstattbindung=False,
            driver_scope="policyholder_only",
            min_driver_age=None,
            named_drivers=[
                {
                    "name": "Maria Gonzalez",
                    "date_of_birth": "1995-05-12",
                    "license_since": "2013-06-15",
                    "relationship": "policyholder"
                }
            ],
            country_coverage=["DE"],
            seasonal_months="04-10",  # April to October
            gross_negligence_waived=False,
            has_telematics=False,
            broker_id=None,
            metadata={
                "underwriter": "DEVK Versicherungen",
                "distribution_channel": "direct",
            }
        )
        session.add(policy4)
        
        # Insurant 5: Peter Müller (Suspended policy - payment overdue)
        insurant5_id = str(uuid4())
        insurant5 = Insurant(
            insurant_id=insurant5_id,
            first_name="Peter",
            last_name="Müller",
            date_of_birth=date(1988, 9, 30),
            email="peter.mueller@example.de",
            phone="+49 221 33344455",
            address_street="Domstraße 99",
            address_city="Köln",
            address_postal_code="50667",
            address_country="DE",
            preferred_language="de",
            preferred_communication_channel="mail",
            has_power_of_attorney=False,
            is_vulnerable_customer=False,
            marketing_consent=False,
            customer_since=date(2021, 9, 1),
            metadata={
                "customer_segment": "standard",
                "nps_score": 4,
            }
        )
        session.add(insurant5)
        
        # Policy 5: Peter's Audi with payment issues
        policy5 = Policy(
            policy_id=str(uuid4()),
            policy_number="POL-2023-007788",
            insurant_id=insurant5_id,
            product_name="KFZ Standard",
            tariff_version="2023.1",
            effective_date=date(2023, 9, 1),
            renewal_date=date(2025, 9, 1),
            status=PolicyStatus.ACTIVE.value,
            annual_premium=1450.00,
            payment_status="overdue",  # Payment issue
            license_plate="K-PM-4321",
            vin="WAUZZZ8V7DA123456",
            vehicle_make="Audi",
            vehicle_model="A4 2.0 TDI",
            first_registration=date(2019, 8, 15),
            engine_power_kw=110,
            fuel_type="Diesel",
            vehicle_value=22000.00,
            current_sum_insured=22000.00,
            use_type=VehicleUseType.PRIVATE.value,
            annual_mileage=20000,
            garage_address="Domstraße 99, 50667 Köln",
            liability_sum=100000000.0,
            has_vollkasko=True,
            has_teilkasko=True,
            deductible_vollkasko=500.0,
            deductible_teilkasko=150.0,
            addons={},
            sf_class_liability="SF5",
            sf_class_vollkasko="SF2",
            has_rabattschutz=False,
            has_werkstattbindung=True,
            driver_scope="policyholder_only",
            min_driver_age=None,
            named_drivers=[
                {
                    "name": "Peter Müller",
                    "date_of_birth": "1988-09-30",
                    "license_since": "2006-10-15",
                    "relationship": "policyholder"
                }
            ],
            country_coverage=["DE", "AT", "CH"],
            seasonal_months=None,
            gross_negligence_waived=False,
            has_telematics=False,
            broker_id=None,
            metadata={
                "underwriter": "Gothaer Versicherung",
                "distribution_channel": "direct",
                "payment_reminder_sent": "2024-04-01",
            }
        )
        session.add(policy5)
        
        await session.commit()
        
        print("\n✅ Mock data generated successfully!")
        print("\n📊 Summary:")
        print(f"  - 5 Insurants created")
        print(f"  - 5 Policies created")
        print(f"  - 2 Claims history records created")
        print("\n📝 Test Scenarios:")
        print(f"  1. Max Mustermann (POL-2024-001234, B-MW-1234) - Active Vollkasko, no claims")
        print(f"  2. Anna Schmidt (POL-2024-005678, M-AS-9876) - Active Teilkasko only")
        print(f"  3. Thomas Weber (POL-2023-009876, HH-TW-5555) - Active with 2 prior claims")
        print(f"  4. Maria Gonzalez (POL-2024-011223, S-MG-777) - Seasonal motorcycle (Apr-Oct)")
        print(f"  5. Peter Müller (POL-2023-007788, K-PM-4321) - Payment overdue")


if __name__ == "__main__":
    asyncio.run(generate_mock_data())