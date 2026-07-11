"""
JSON Schema定義
2段階方式: Phase1(OCR抽出) → Phase2(後処理で正規化)

設計方針:
- strict=True の場合、required に全プロパティを含める必要がある
- 型は ["string", "null"] で不明時はnullを許可（これで「取れなければnull」が実現）
- 分解フィールドは廃止し、rawで取得
- 後処理で正規表現等を使って分解
"""

# =============================================================================
# Phase 1: OCR抽出用スキーマ（壊れにくい設計）
# =============================================================================

# 物件概要用スキーマ（OCR抽出）
OVERVIEW_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "property_overview_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                # 基本情報（raw）
                "property_name": {"type": ["string", "null"], "description": "物件名"},
                "price_raw": {"type": ["string", "null"], "description": "価格（原文のまま、例: 1億2,000万円）"},
                "info_date_raw": {"type": ["string", "null"], "description": "情報入手日（原文のまま）"},
                "info_source": {"type": ["string", "null"], "description": "情報入手先"},
                "info_source_contact": {"type": ["string", "null"], "description": "物件担当者の人名（電話番号ではなく人名）"},
                
                # 所在地（raw）
                "address_display": {"type": ["string", "null"], "description": "住居表示（補足情報含む）"},
                "address_lot": {"type": ["string", "null"], "description": "地番"},
                
                # 交通（raw - 1行で取得、後処理で分解）
                "transport_1_raw": {"type": ["string", "null"], "description": "交通1（原文、例: 東京メトロ日比谷線「六本木」駅 徒歩2分）"},
                "transport_1_line": {"type": ["string", "null"], "description": "交通1の路線名のみ（沿線名セルの文字だけを転記）"},
                "transport_2_raw": {"type": ["string", "null"], "description": "交通2（原文）"},
                "transport_2_line": {"type": ["string", "null"], "description": "交通2の路線名のみ"},
                "transport_3_raw": {"type": ["string", "null"], "description": "交通3（原文）"},
                "transport_3_line": {"type": ["string", "null"], "description": "交通3の路線名のみ"},
                
                # 土地情報（raw）
                "land_area_raw": {"type": ["string", "null"], "description": "地積（原文、例: 150.00㎡(公簿)）"},
                "land_category": {"type": ["string", "null"], "description": "地目"},
                
                # 道路情報（raw）- 重要
                "road_1_raw": {"type": ["string", "null"], "description": "道路1（接面道路/前面道路行から抽出、例: 南西側 公道、北側6m公道。方位は北東/北西/南東/南西/北/南/東/西の8方位。2文字方位を1文字に省略しないこと）"},
                "road_2_raw": {"type": ["string", "null"], "description": "道路2（2面道路の場合に抽出、なければnull）"},
                
                # 用途地域等（raw）
                "use_district_raw": {"type": ["string", "null"], "description": "用途地域（原文、複数ある場合はカンマ区切り）"},
                "building_coverage_ratio_raw": {"type": ["string", "null"], "description": "建蔽率（原文、例: 60%）"},
                "floor_area_ratio_raw": {"type": ["string", "null"], "description": "容積率（原文、例: 200%）"},
                
                # 公法規制その他
                "regulation_other": {"type": ["string", "null"], "description": "公法規制の「その他」欄（地区計画等、原文のまま。例: 広尾五丁目地区計画）"},
                
                # 建物情報（raw）
                "building_type": {"type": ["string", "null"], "description": "建物種類"},
                "building_structure": {"type": ["string", "null"], "description": "建物構造"},
                "building_area_raw": {"type": ["string", "null"], "description": "延べ床面積（原文。階数ごとの面積がある場合は改行区切りで全階分を含めること。例: '1階 124:86\\n2階 150:00'、'1階部分 57:24\\n2階部分 43:30'）"},
                "exclusive_area_raw": {"type": ["string", "null"], "description": "専有面積（原文）"},
                "construction_date_raw": {"type": ["string", "null"], "description": "築年月（原文、例: 平成10年3月）"},
                
                # 価格フラグ（boolean）
                "price_is_consultation": {"type": ["boolean", "null"], "description": "価格が「相談」か"},
                "price_is_unknown": {"type": ["boolean", "null"], "description": "価格が「不明」か"},
                "price_is_bid": {"type": ["boolean", "null"], "description": "価格が「入札」か"},
                "price_is_negotiation": {"type": ["boolean", "null"], "description": "価格が「協議」か"},
                
                # 備考（最重要）
                "remarks": {"type": ["string", "null"], "description": "備考欄（原文のまま、改行を保持）"},
                
                # 診断情報
                "unreadable_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "読み取れなかった箇所のリスト（空配列OK）"
                },
                "extraction_notes": {"type": ["string", "null"], "description": "抽出時の補足・注意事項（必ず何か書く）"}
            },
            "required": [
                "property_name", "price_raw", "info_date_raw", "info_source", "info_source_contact",
                "address_display", "address_lot",
                "transport_1_raw", "transport_1_line", "transport_2_raw", "transport_2_line", "transport_3_raw", "transport_3_line",
                "land_area_raw", "land_category", "road_1_raw", "road_2_raw",
                "use_district_raw", "building_coverage_ratio_raw", "floor_area_ratio_raw",
                "regulation_other",
                "building_type", "building_structure", "building_area_raw", "exclusive_area_raw", "construction_date_raw",
                "price_is_consultation", "price_is_unknown", "price_is_bid", "price_is_negotiation",
                "remarks", "unreadable_segments", "extraction_notes"
            ],
            "additionalProperties": False
        }
    }
}

# 開発物件用スキーマ（OCR抽出）- 大幅改善版
DEVELOPMENT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "property_development_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                # 基本情報
                "property_name": {"type": ["string", "null"], "description": "物件名"},
                "price_raw": {"type": ["string", "null"], "description": "価格（原文、---は null）"},
                "info_date_raw": {"type": ["string", "null"], "description": "情報入手日/本書作成日（原文）"},
                "info_source": {"type": ["string", "null"], "description": "情報入手先/仲介会社"},
                "info_source_contact": {"type": ["string", "null"], "description": "物件担当者の人名（電話番号ではなく人名）"},
                
                # 所在地
                "address_display": {"type": ["string", "null"], "description": "住居表示"},
                "address_lot": {"type": ["string", "null"], "description": "地番"},
                
                # 現況
                "current_status": {"type": ["string", "null"], "description": "現況（賃貸中、更地渡し等）"},
                
                # 交通（raw）
                "transport_1_raw": {"type": ["string", "null"], "description": "交通1（原文）"},
                "transport_1_line": {"type": ["string", "null"], "description": "交通1の路線名のみ（沿線名セルの文字だけを転記）"},
                "transport_2_raw": {"type": ["string", "null"], "description": "交通2（原文）"},
                "transport_2_line": {"type": ["string", "null"], "description": "交通2の路線名のみ"},
                "transport_3_raw": {"type": ["string", "null"], "description": "交通3（原文）"},
                "transport_3_line": {"type": ["string", "null"], "description": "交通3の路線名のみ"},
                
                # 土地情報
                "land_area_official_raw": {"type": ["string", "null"], "description": "地積（公簿/登記面積）原文（複数筆ある場合は改行区切りで全件含めること。例: '37:45\\n210:57\\n105:28'、'210.56 ㎡'）"},
                "land_area_measured_raw": {"type": ["string", "null"], "description": "地積（実測）原文"},
                "effective_land_area_official_raw": {"type": ["string", "null"], "description": "有効地積（公簿）原文"},
                "effective_land_area_measured_raw": {"type": ["string", "null"], "description": "有効地積（実測）原文"},
                "land_category": {"type": ["string", "null"], "description": "地目"},
                
                # 道路情報（raw）
                "road_1_raw": {"type": ["string", "null"], "description": "道路1（原文。方位は北東/北西/南東/南西/北/南/東/西の8方位。2文字方位を1文字に省略しないこと）"},
                "road_2_raw": {"type": ["string", "null"], "description": "道路2（原文。同上）"},
                
                # 用途地域等（建蔽率/容積率は別フィールド）
                "use_district_1_raw": {"type": ["string", "null"], "description": "用途地域1"},
                "use_district_2_raw": {"type": ["string", "null"], "description": "用途地域2"},
                "building_coverage_ratio_1_raw": {"type": ["string", "null"], "description": "建蔽率1（例: 60%）"},
                "building_coverage_ratio_2_raw": {"type": ["string", "null"], "description": "建蔽率2"},
                "floor_area_ratio_1_raw": {"type": ["string", "null"], "description": "容積率1（例: 300%）"},
                "floor_area_ratio_2_raw": {"type": ["string", "null"], "description": "容積率2"},
                "height_district_1_raw": {"type": ["string", "null"], "description": "高度指定1（原文）"},
                "height_district_2_raw": {"type": ["string", "null"], "description": "高度指定2（原文）"},
                "fire_district_1_raw": {"type": ["string", "null"], "description": "防火指定1（原文）"},
                "fire_district_2_raw": {"type": ["string", "null"], "description": "防火指定2（原文）"},
                
                # 公法規制その他
                "regulation_other": {"type": ["string", "null"], "description": "公法規制の「その他」欄（地区計画等、原文のまま）"},
                
                # 既存建物情報（複数件対応 - 最大5件）
                "existing_buildings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "building_type": {"type": ["string", "null"], "description": "建物種類/用途（例: 店舗・事務所・共同住宅）"},
                            "building_structure": {"type": ["string", "null"], "description": "建物構造（例: 鉄筋コンクリート造陸屋根7階建）"},
                            "building_area_raw": {"type": ["string", "null"], "description": "延べ床面積（原文。階数ごとの面積がある場合は改行区切りで全階分を含めること。例: '1階 124:86\\n2階 150:00\\n3階 120:00'、'1階部分 57:24\\n2階部分 43:30'）"},
                            "construction_date_raw": {"type": ["string", "null"], "description": "築年月（原文）"},
                            "inspection_certificate": {"type": ["string", "null"], "description": "検査済証の有無"}
                        },
                        "required": ["building_type", "building_structure", "building_area_raw", "construction_date_raw", "inspection_certificate"],
                        "additionalProperties": False
                    },
                    "description": "既存建物情報（複数棟ある場合は全件抽出、最大5件）"
                },
                
                # 建物計画情報
                "planned_building_structure": {"type": ["string", "null"], "description": "計画建物構造"},
                "planned_building_area_raw": {"type": ["string", "null"], "description": "計画延べ床面積（原文）"},
                
                # 価格関連情報
                "land_price_per_sqm_raw": {"type": ["string", "null"], "description": "路線価（例: 1,840千円/㎡）"},
                "unit_price_official_raw": {"type": ["string", "null"], "description": "坪単価-地積（公簿）（価格÷坪数の金額。例: 1,960万円/坪。※「約25.06坪」等の面積の坪換算値ではない。坪単価欄に金額が記載されている場合のみ抽出）"},
                "unit_price_measured_raw": {"type": ["string", "null"], "description": "坪単価-地積（実測）（価格÷坪数の金額。例: 1,960万円/坪。※「約24.96坪」等の面積の坪換算値ではない。坪単価欄に金額が記載されている場合のみ抽出）"},
                "yield_rate_raw": {"type": ["string", "null"], "description": "利回り（例: 5.5%）"},
                "land_valuation_raw": {"type": ["string", "null"], "description": "土地評価額"},
                "building_valuation_raw": {"type": ["string", "null"], "description": "建物評価額"},
                
                # 費用情報
                "property_tax_raw": {"type": ["string", "null"], "description": "固定資産税（年間）"},
                "building_management_fee_raw": {"type": ["string", "null"], "description": "建物管理費（年間）"},
                "bm_fee_raw": {"type": ["string", "null"], "description": "BM費"},
                "pm_fee_raw": {"type": ["string", "null"], "description": "PM費"},
                "insurance_fee_raw": {"type": ["string", "null"], "description": "保険料（年間）"},
                
                # 価格フラグ（boolean）
                "price_is_consultation": {"type": ["boolean", "null"], "description": "価格が「相談」か"},
                "price_is_unknown": {"type": ["boolean", "null"], "description": "価格が「不明」か"},
                "price_is_bid": {"type": ["boolean", "null"], "description": "価格が「入札」か"},
                "price_is_negotiation": {"type": ["boolean", "null"], "description": "価格が「協議」か"},
                
                # 備考
                "remarks": {"type": ["string", "null"], "description": "備考欄・注意事項（原文、改行保持）"},
                
                # 診断情報
                "unreadable_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "読み取れなかった箇所（空配列OK）"
                },
                "extraction_notes": {"type": ["string", "null"], "description": "抽出時の補足"}
            },
            "required": [
                "property_name", "price_raw", "info_date_raw", "info_source", "info_source_contact",
                "address_display", "address_lot", "current_status",
                "transport_1_raw", "transport_1_line", "transport_2_raw", "transport_2_line", "transport_3_raw", "transport_3_line",
                "land_area_official_raw", "land_area_measured_raw",
                "effective_land_area_official_raw", "effective_land_area_measured_raw", "land_category",
                "road_1_raw", "road_2_raw",
                "use_district_1_raw", "use_district_2_raw",
                "building_coverage_ratio_1_raw", "building_coverage_ratio_2_raw",
                "floor_area_ratio_1_raw", "floor_area_ratio_2_raw",
                "height_district_1_raw", "height_district_2_raw",
                "fire_district_1_raw", "fire_district_2_raw",
                "regulation_other",
                "price_is_consultation", "price_is_unknown", "price_is_bid", "price_is_negotiation",
                "existing_buildings",
                "planned_building_structure", "planned_building_area_raw",
                "land_price_per_sqm_raw", "unit_price_official_raw", "unit_price_measured_raw",
                "yield_rate_raw", "land_valuation_raw", "building_valuation_raw",
                "property_tax_raw", "building_management_fee_raw", "bm_fee_raw", "pm_fee_raw", "insurance_fee_raw",
                "remarks", "unreadable_segments", "extraction_notes"
            ],
            "additionalProperties": False
        }
    }
}

# 区分物件用スキーマ（OCR抽出）
UNIT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "property_unit_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                # 基本情報
                "property_name": {"type": ["string", "null"], "description": "物件名"},
                "price_raw": {"type": ["string", "null"], "description": "価格（原文）"},
                "info_date_raw": {"type": ["string", "null"], "description": "情報入手日（原文）"},
                "info_source": {"type": ["string", "null"], "description": "情報入手先"},
                "info_source_contact": {"type": ["string", "null"], "description": "物件担当者の人名（電話番号ではなく人名）"},
                
                # 所在地
                "address_display": {"type": ["string", "null"], "description": "住居表示"},
                "address_lot": {"type": ["string", "null"], "description": "地番"},
                
                # 交通（raw）
                "transport_1_raw": {"type": ["string", "null"], "description": "交通1（原文）"},
                "transport_1_line": {"type": ["string", "null"], "description": "交通1の路線名のみ（沿線名セルの文字だけを転記）"},
                "transport_2_raw": {"type": ["string", "null"], "description": "交通2（原文）"},
                "transport_2_line": {"type": ["string", "null"], "description": "交通2の路線名のみ"},
                "transport_3_raw": {"type": ["string", "null"], "description": "交通3（原文）"},
                "transport_3_line": {"type": ["string", "null"], "description": "交通3の路線名のみ"},
                
                # 専有部分情報
                "exclusive_area_raw": {"type": ["string", "null"], "description": "専有面積（原文）"},
                "balcony_area_raw": {"type": ["string", "null"], "description": "バルコニー面積（原文）"},
                "floor_number": {"type": ["string", "null"], "description": "所在階"},
                "total_floors": {"type": ["string", "null"], "description": "建物階数"},
                "floor_plan": {"type": ["string", "null"], "description": "間取り（例: 2LDK, 3SLDK, 1R）"},
                
                # 開口向（バルコニー方向）
                "opening_direction": {"type": ["string", "null"], "description": "開口向またはバルコニー方向（北/東/南/西/北東/南東/南西/北西）"},
                
                # リノベーション情報
                "renovation_raw": {"type": ["string", "null"], "description": "リノベーション・リフォーム情報（原文のまま、例: フルリノベーション実施※2025年12月完成予定、リフォーム済、リノベ済）"},
                
                # 建物情報
                "building_structure": {"type": ["string", "null"], "description": "建物構造"},
                "construction_date_raw": {"type": ["string", "null"], "description": "築年月（原文）"},
                "total_units": {"type": ["string", "null"], "description": "総戸数"},
                
                # 管理情報
                "management_form": {"type": ["string", "null"], "description": "管理形態"},
                "management_fee_raw": {"type": ["string", "null"], "description": "管理費（原文）"},
                "repair_reserve_fund_raw": {"type": ["string", "null"], "description": "修繕積立金（原文）"},
                
                # 敷地権情報
                "land_area_raw": {"type": ["string", "null"], "description": "敷地面積（原文）"},
                "land_rights": {"type": ["string", "null"], "description": "土地権利"},
                
                # 用途地域等
                "use_district_1_raw": {"type": ["string", "null"], "description": "用途地域1（用途地域名のみ、例: 商業地域、第一種住居地域）"},
                "use_district_2_raw": {"type": ["string", "null"], "description": "用途地域2（同上、あれば）"},
                "building_coverage_ratio_1_raw": {"type": ["string", "null"], "description": "建蔽率1（例: 60%）"},
                "building_coverage_ratio_2_raw": {"type": ["string", "null"], "description": "建蔽率2"},
                "floor_area_ratio_1_raw": {"type": ["string", "null"], "description": "容積率1（例: 300%）"},
                "floor_area_ratio_2_raw": {"type": ["string", "null"], "description": "容積率2"},
                "height_district_1_raw": {"type": ["string", "null"], "description": "高度指定1（原文）"},
                "height_district_2_raw": {"type": ["string", "null"], "description": "高度指定2（原文）"},
                "fire_district_1_raw": {"type": ["string", "null"], "description": "防火指定1（原文、例: 準防火地域）"},
                "fire_district_2_raw": {"type": ["string", "null"], "description": "防火指定2（原文）"},
                
                # 公法規制その他
                "regulation_other": {"type": ["string", "null"], "description": "公法規制の「その他」欄（地区計画等、原文のまま）"},
                
                # 建物種類
                "building_type": {"type": ["string", "null"], "description": "建物種類/用途（例: 共同住宅、居宅）"},
                
                # 検査済証
                "inspection_certificate": {"type": ["string", "null"], "description": "検査済証の有無"},
                
                # 現況
                "current_status": {"type": ["string", "null"], "description": "現況"},
                
                # 価格フラグ（boolean）
                "price_is_consultation": {"type": ["boolean", "null"], "description": "価格が「相談」か"},
                "price_is_unknown": {"type": ["boolean", "null"], "description": "価格が「不明」か"},
                "price_is_bid": {"type": ["boolean", "null"], "description": "価格が「入札」か"},
                "price_is_negotiation": {"type": ["boolean", "null"], "description": "価格が「協議」か"},
                
                # 備考
                "remarks": {"type": ["string", "null"], "description": "備考欄（原文）"},
                
                # 診断情報
                "unreadable_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "読み取れなかった箇所（空配列OK）"
                },
                "extraction_notes": {"type": ["string", "null"], "description": "抽出時の補足"}
            },
            "required": [
                "property_name", "price_raw", "info_date_raw", "info_source", "info_source_contact",
                "address_display", "address_lot",
                "transport_1_raw", "transport_1_line", "transport_2_raw", "transport_2_line", "transport_3_raw", "transport_3_line",
                "exclusive_area_raw", "balcony_area_raw", "floor_number", "total_floors", "floor_plan",
                "opening_direction", "renovation_raw",
                "building_type", "building_structure", "construction_date_raw", "total_units",
                "inspection_certificate",
                "management_form", "management_fee_raw", "repair_reserve_fund_raw",
                "land_area_raw", "land_rights",
                "use_district_1_raw", "use_district_2_raw",
                "building_coverage_ratio_1_raw", "building_coverage_ratio_2_raw",
                "floor_area_ratio_1_raw", "floor_area_ratio_2_raw",
                "height_district_1_raw", "height_district_2_raw",
                "fire_district_1_raw", "fire_district_2_raw",
                "regulation_other",
                "price_is_consultation", "price_is_unknown", "price_is_bid", "price_is_negotiation",
                "current_status", "remarks", "unreadable_segments", "extraction_notes"
            ],
            "additionalProperties": False
        }
    }
}

# 収益転売物件用スキーマ（OCR抽出）
INCOME_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "property_income_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                # 基本情報
                "property_name": {"type": ["string", "null"], "description": "物件名"},
                "price_raw": {"type": ["string", "null"], "description": "価格（原文）"},
                "info_date_raw": {"type": ["string", "null"], "description": "情報入手日（原文）"},
                "info_source": {"type": ["string", "null"], "description": "情報入手先"},
                "info_source_contact": {"type": ["string", "null"], "description": "物件担当者の人名（電話番号ではなく人名）"},
                
                # 所在地
                "address_display": {"type": ["string", "null"], "description": "住居表示"},
                "address_lot": {"type": ["string", "null"], "description": "地番"},
                
                # 交通（raw）
                "transport_1_raw": {"type": ["string", "null"], "description": "交通1（原文）"},
                "transport_1_line": {"type": ["string", "null"], "description": "交通1の路線名のみ（沿線名セルの文字だけを転記）"},
                "transport_2_raw": {"type": ["string", "null"], "description": "交通2（原文）"},
                "transport_2_line": {"type": ["string", "null"], "description": "交通2の路線名のみ"},
                "transport_3_raw": {"type": ["string", "null"], "description": "交通3（原文）"},
                "transport_3_line": {"type": ["string", "null"], "description": "交通3の路線名のみ"},
                
                # 土地情報
                "land_area_official_raw": {"type": ["string", "null"], "description": "地積（公簿）原文（複数筆ある場合は改行区切りで全件含めること。例: '37:45\\n210:57\\n105:28'、'210.56 ㎡'）"},
                "land_area_measured_raw": {"type": ["string", "null"], "description": "地積（実測）原文"},
                "land_category": {"type": ["string", "null"], "description": "地目"},
                
                # 道路情報
                "road_1_raw": {"type": ["string", "null"], "description": "道路1（原文。方位は北東/北西/南東/南西/北/南/東/西の8方位。2文字方位を1文字に省略しないこと）"},
                "road_2_raw": {"type": ["string", "null"], "description": "道路2（原文。同上）"},
                
                # 用途地域等（建蔽率/容積率は別フィールドで抽出）
                "use_district_1_raw": {"type": ["string", "null"], "description": "用途地域1（用途地域名のみ、例: 商業地域、第一種住居地域）"},
                "use_district_2_raw": {"type": ["string", "null"], "description": "用途地域2（同上、あれば）"},
                "building_coverage_ratio_1_raw": {"type": ["string", "null"], "description": "建蔽率1（例: 60%）"},
                "building_coverage_ratio_2_raw": {"type": ["string", "null"], "description": "建蔽率2"},
                "floor_area_ratio_1_raw": {"type": ["string", "null"], "description": "容積率1（例: 300%）"},
                "floor_area_ratio_2_raw": {"type": ["string", "null"], "description": "容積率2"},
                "height_district_1_raw": {"type": ["string", "null"], "description": "高度指定1（原文、例: 30m第3種高度地区）"},
                "height_district_2_raw": {"type": ["string", "null"], "description": "高度指定2（原文）"},
                "fire_district_1_raw": {"type": ["string", "null"], "description": "防火指定1（原文、例: 準防火地域）"},
                "fire_district_2_raw": {"type": ["string", "null"], "description": "防火指定2（原文）"},
                
                # 公法規制その他
                "regulation_other": {"type": ["string", "null"], "description": "公法規制の「その他」欄（地区計画等、原文のまま）"},
                
                # 建物情報
                "building_type": {"type": ["string", "null"], "description": "建物種類/用途（例: 一棟マンション、共同住宅、事務所）"},
                "building_structure": {"type": ["string", "null"], "description": "建物構造"},
                "building_area_raw": {"type": ["string", "null"], "description": "延べ床面積（原文。階数ごとの面積がある場合は改行区切りで全階分を含めること。例: '1階 124:86\\n2階 150:00'、'1階部分 57:24\\n2階部分 43:30'）"},
                "construction_date_raw": {"type": ["string", "null"], "description": "築年月（原文）"},
                "total_units": {"type": ["string", "null"], "description": "総戸数"},
                
                # 検査済証
                "inspection_certificate": {"type": ["string", "null"], "description": "検査済証の有無"},
                
                # 価格関連情報
                "land_price_per_sqm_raw": {"type": ["string", "null"], "description": "路線価（例: 1,840千円/㎡）"},
                
                # 価格フラグ（boolean）
                "price_is_consultation": {"type": ["boolean", "null"], "description": "価格が「相談」か"},
                "price_is_unknown": {"type": ["boolean", "null"], "description": "価格が「不明」か"},
                "price_is_bid": {"type": ["boolean", "null"], "description": "価格が「入札」か"},
                "price_is_negotiation": {"type": ["boolean", "null"], "description": "価格が「協議」か"},
                
                # 収益情報
                "current_rent_income_raw": {"type": ["string", "null"], "description": "現行賃料収入（原文）"},
                "current_occupancy_rate": {"type": ["string", "null"], "description": "現行稼働率"},
                
                # 現況
                "current_status": {"type": ["string", "null"], "description": "現況"},
                
                # 備考
                "remarks": {"type": ["string", "null"], "description": "備考欄（原文）"},
                
                # 診断情報
                "unreadable_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "読み取れなかった箇所（空配列OK）"
                },
                "extraction_notes": {"type": ["string", "null"], "description": "抽出時の補足"}
            },
            "required": [
                "property_name", "price_raw", "info_date_raw", "info_source", "info_source_contact",
                "address_display", "address_lot",
                "transport_1_raw", "transport_1_line", "transport_2_raw", "transport_2_line", "transport_3_raw", "transport_3_line",
                "land_area_official_raw", "land_area_measured_raw", "land_category",
                "road_1_raw", "road_2_raw",
                "use_district_1_raw", "use_district_2_raw",
                "building_coverage_ratio_1_raw", "building_coverage_ratio_2_raw",
                "floor_area_ratio_1_raw", "floor_area_ratio_2_raw",
                "height_district_1_raw", "height_district_2_raw",
                "fire_district_1_raw", "fire_district_2_raw",
                "regulation_other",
                "price_is_consultation", "price_is_unknown", "price_is_bid", "price_is_negotiation",
                "building_type", "building_structure", "building_area_raw", "construction_date_raw", "total_units",
                "inspection_certificate", "land_price_per_sqm_raw",
                "current_rent_income_raw", "current_occupancy_rate",
                "current_status", "remarks", "unreadable_segments", "extraction_notes"
            ],
            "additionalProperties": False
        }
    }
}

# 土地転売物件用スキーマ（OCR抽出）
LAND_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "property_land_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                # 基本情報
                "property_name": {"type": ["string", "null"], "description": "物件名"},
                "price_raw": {"type": ["string", "null"], "description": "価格（原文）"},
                "info_date_raw": {"type": ["string", "null"], "description": "情報入手日（原文）"},
                "info_source": {"type": ["string", "null"], "description": "情報入手先"},
                "info_source_contact": {"type": ["string", "null"], "description": "物件担当者の人名（電話番号ではなく人名）"},
                
                # 所在地
                "address_display": {"type": ["string", "null"], "description": "住居表示"},
                "address_lot": {"type": ["string", "null"], "description": "地番"},
                
                # 現況
                "current_status": {"type": ["string", "null"], "description": "現況（現況渡し（建物有）/更地渡し）"},
                
                # 交通（raw）
                "transport_1_raw": {"type": ["string", "null"], "description": "交通1（原文）"},
                "transport_1_line": {"type": ["string", "null"], "description": "交通1の路線名のみ（沿線名セルの文字だけを転記）"},
                "transport_2_raw": {"type": ["string", "null"], "description": "交通2（原文）"},
                "transport_2_line": {"type": ["string", "null"], "description": "交通2の路線名のみ"},
                "transport_3_raw": {"type": ["string", "null"], "description": "交通3（原文）"},
                "transport_3_line": {"type": ["string", "null"], "description": "交通3の路線名のみ"},
                
                # 土地情報
                "land_area_official_raw": {"type": ["string", "null"], "description": "地積（公簿）原文（複数筆ある場合は改行区切りで全件含めること。例: '37:45\\n210:57\\n105:28'、'210.56 ㎡'）"},
                "land_area_measured_raw": {"type": ["string", "null"], "description": "地積（実測）原文"},
                "land_category": {"type": ["string", "null"], "description": "地目"},
                
                # 道路情報（raw）
                "road_1_raw": {"type": ["string", "null"], "description": "道路1（原文。方位は北東/北西/南東/南西/北/南/東/西の8方位。2文字方位を1文字に省略しないこと）"},
                "road_2_raw": {"type": ["string", "null"], "description": "道路2（原文。同上）"},
                
                # 用途地域等（複数対応、raw）
                "use_district_1_raw": {"type": ["string", "null"], "description": "用途地域1（用途地域名のみ、例: 商業地域、第一種住居地域）"},
                "use_district_2_raw": {"type": ["string", "null"], "description": "用途地域2"},
                "use_district_3_raw": {"type": ["string", "null"], "description": "用途地域3"},
                "building_coverage_ratio_1_raw": {"type": ["string", "null"], "description": "建蔽率1（例: 80%）"},
                "building_coverage_ratio_2_raw": {"type": ["string", "null"], "description": "建蔽率2"},
                "floor_area_ratio_1_raw": {"type": ["string", "null"], "description": "容積率1（例: 400%）"},
                "floor_area_ratio_2_raw": {"type": ["string", "null"], "description": "容積率2"},
                "height_district_1_raw": {"type": ["string", "null"], "description": "高度指定1（原文、例: 24m第3種高度地区）"},
                "height_district_2_raw": {"type": ["string", "null"], "description": "高度指定2（原文）"},
                "fire_district_1_raw": {"type": ["string", "null"], "description": "防火指定1（原文、例: 準防火地域）"},
                "fire_district_2_raw": {"type": ["string", "null"], "description": "防火指定2（原文）"},
                
                # 公法規制その他
                "regulation_other": {"type": ["string", "null"], "description": "公法規制の「その他」欄（地区計画等、原文のまま）"},
                
                # 既存建物情報
                "building_type": {"type": ["string", "null"], "description": "建物種類/用途（例: 住宅、店舗・事務所・共同住宅）"},
                "building_structure": {"type": ["string", "null"], "description": "建物構造（例: RC(鉄筋コンクリート造)）"},
                "building_area_raw": {"type": ["string", "null"], "description": "延べ床面積（原文。階数ごとの面積がある場合は改行区切りで全階分を含めること。例: '1階 124:86\\n2階 150:00'、'1階部分 57:24\\n2階部分 43:30'）"},
                "construction_date_raw": {"type": ["string", "null"], "description": "築年月（原文）"},
                
                # 検査済証
                "inspection_certificate": {"type": ["string", "null"], "description": "検査済証の有無"},
                
                # 価格関連情報
                "land_price_per_sqm_raw": {"type": ["string", "null"], "description": "路線価（例: 1,840千円/㎡）"},
                "unit_price_official_raw": {"type": ["string", "null"], "description": "坪単価-地積（公簿）（価格÷坪数の金額。例: 1,960万円/坪。※「約25.06坪」等の面積の坪換算値ではない。坪単価欄に金額が記載されている場合のみ抽出）"},
                "unit_price_measured_raw": {"type": ["string", "null"], "description": "坪単価-地積（実測）（価格÷坪数の金額。例: 1,960万円/坪。※「約24.96坪」等の面積の坪換算値ではない。坪単価欄に金額が記載されている場合のみ抽出）"},
                "land_valuation_raw": {"type": ["string", "null"], "description": "土地評価額"},
                "building_valuation_raw": {"type": ["string", "null"], "description": "建物評価額"},
                
                # 費用情報
                "property_tax_raw": {"type": ["string", "null"], "description": "固定資産税（年間）"},
                "building_management_fee_raw": {"type": ["string", "null"], "description": "建物管理費（年間）"},
                "pm_fee_raw": {"type": ["string", "null"], "description": "PM費"},
                "insurance_fee_raw": {"type": ["string", "null"], "description": "保険料（年間）"},
                
                # 価格フラグ（boolean）
                "price_is_consultation": {"type": ["boolean", "null"], "description": "価格が「相談」か"},
                "price_is_unknown": {"type": ["boolean", "null"], "description": "価格が「不明」か"},
                "price_is_bid": {"type": ["boolean", "null"], "description": "価格が「入札」か"},
                "price_is_negotiation": {"type": ["boolean", "null"], "description": "価格が「協議」か"},
                
                # 備考
                "remarks": {"type": ["string", "null"], "description": "備考欄（原文）"},
                
                # 診断情報
                "unreadable_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "読み取れなかった箇所（空配列OK）"
                },
                "extraction_notes": {"type": ["string", "null"], "description": "抽出時の補足"}
            },
            "required": [
                "property_name", "price_raw", "info_date_raw", "info_source", "info_source_contact",
                "address_display", "address_lot", "current_status",
                "transport_1_raw", "transport_1_line", "transport_2_raw", "transport_2_line", "transport_3_raw", "transport_3_line",
                "land_area_official_raw", "land_area_measured_raw", "land_category",
                "road_1_raw", "road_2_raw",
                "use_district_1_raw", "use_district_2_raw", "use_district_3_raw",
                "building_coverage_ratio_1_raw", "building_coverage_ratio_2_raw",
                "floor_area_ratio_1_raw", "floor_area_ratio_2_raw",
                "height_district_1_raw", "height_district_2_raw",
                "fire_district_1_raw", "fire_district_2_raw",
                "regulation_other",
                "building_type", "building_structure", "building_area_raw", "construction_date_raw",
                "inspection_certificate",
                "land_price_per_sqm_raw", "unit_price_official_raw", "unit_price_measured_raw",
                "land_valuation_raw", "building_valuation_raw",
                "property_tax_raw", "building_management_fee_raw", "pm_fee_raw", "insurance_fee_raw",
                "price_is_consultation", "price_is_unknown", "price_is_bid", "price_is_negotiation",
                "remarks", "unreadable_segments", "extraction_notes"
            ],
            "additionalProperties": False
        }
    }
}


def get_schema(property_type: str):
    """物件タイプに応じたスキーマを取得"""
    schema_map = {
        'overview': OVERVIEW_SCHEMA,
        'development': DEVELOPMENT_SCHEMA,
        'unit': UNIT_SCHEMA,
        'income': INCOME_SCHEMA,
        'land': LAND_SCHEMA,
    }
    return schema_map.get(property_type, OVERVIEW_SCHEMA)
