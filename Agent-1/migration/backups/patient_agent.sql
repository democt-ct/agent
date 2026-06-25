--
-- PostgreSQL database dump
--

\restrict pnle0J2c7SVUvA06TEqYXK8gRLDVQnMwC7EkJ6zP7KoIG5HjenxJxV4jWDWjPSM

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_log (
    id character varying(36) NOT NULL,
    patient_id character varying(36),
    hospital_id character varying(64),
    endpoint character varying(255) NOT NULL,
    method character varying(10) NOT NULL,
    action character varying(50) NOT NULL,
    status_code character varying(10),
    client_ip character varying(50),
    auth_verified character varying(10),
    details text,
    duration_ms double precision,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.audit_log OWNER TO postgres;

--
-- Name: medical_records; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.medical_records (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    record_type character varying(50) NOT NULL,
    title character varying(150) NOT NULL,
    department character varying(100),
    doctor_name character varying(100),
    chief_complaint text,
    present_illness text,
    diagnosis text,
    treatment_plan text,
    medications text,
    notes text,
    record_date timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.medical_records OWNER TO postgres;

--
-- Name: memory_business_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_business_profiles (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    profile_summary text NOT NULL,
    risk_focus character varying(255),
    focus_topics text,
    care_needs text,
    source_summary text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_business_profiles OWNER TO postgres;

--
-- Name: memory_conversation_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_conversation_messages (
    id character varying(36) NOT NULL,
    session_id character varying(64) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_conversation_messages OWNER TO postgres;

--
-- Name: memory_conversation_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_conversation_profiles (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    profile_summary text NOT NULL,
    communication_preference character varying(255),
    focus_topics text,
    source_summary text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_conversation_profiles OWNER TO postgres;

--
-- Name: memory_key_events_v2; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_key_events_v2 (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    type character varying(64) NOT NULL,
    content text NOT NULL,
    impact text NOT NULL,
    confidence double precision NOT NULL,
    source_type character varying(50) NOT NULL,
    source_ref character varying(64),
    evidence text,
    canonical_key character varying(255) NOT NULL,
    status character varying(20) NOT NULL,
    priority character varying(20) NOT NULL,
    tags text,
    event_time timestamp without time zone,
    last_confirmed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_key_events_v2 OWNER TO postgres;

--
-- Name: memory_knowledge_chunks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_knowledge_chunks (
    id character varying(36) NOT NULL,
    hospital_id character varying(64),
    domain character varying(64) NOT NULL,
    title character varying(255) NOT NULL,
    chunk_text text NOT NULL,
    source_type character varying(50) NOT NULL,
    source_ref character varying(128),
    version character varying(64),
    confidence double precision NOT NULL,
    tags text,
    embedding_key character varying(128),
    effective_from timestamp without time zone,
    expires_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_knowledge_chunks OWNER TO postgres;

--
-- Name: memory_preferences; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_preferences (
    id character varying(64) NOT NULL,
    patient_id character varying(64) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    answer_style character varying(32) NOT NULL,
    answer_length character varying(32) NOT NULL,
    tone_style character varying(32) NOT NULL,
    medical_term_level character varying(32) NOT NULL,
    risk_alert_level character varying(32) NOT NULL,
    preferred_language character varying(32) NOT NULL,
    prefer_summary_first boolean NOT NULL,
    prefer_step_by_step boolean NOT NULL,
    notes text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_preferences OWNER TO postgres;

--
-- Name: memory_session_buffer_messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_session_buffer_messages (
    id character varying(36) NOT NULL,
    session_id character varying(64) NOT NULL,
    hospital_id character varying(64),
    role character varying(20) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_session_buffer_messages OWNER TO postgres;

--
-- Name: memory_user_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_user_profiles (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    profile_summary text NOT NULL,
    communication_preference character varying(50),
    risk_focus character varying(255),
    focus_topics text,
    care_needs text,
    source_summary text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.memory_user_profiles OWNER TO postgres;

--
-- Name: patients; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.patients (
    id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    patient_code character varying(64) NOT NULL,
    full_name character varying(100) NOT NULL,
    gender character varying(20),
    birth_date date,
    phone character varying(30),
    id_number_hash character varying(64),
    id_number_last4 character varying(4),
    address character varying(255),
    emergency_contact_name character varying(100),
    emergency_contact_phone character varying(30),
    blood_type character varying(10),
    allergy_history text,
    family_history text,
    notes text,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.patients OWNER TO postgres;

--
-- Name: visit_records; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.visit_records (
    id character varying(36) NOT NULL,
    patient_id character varying(36) NOT NULL,
    hospital_id character varying(64) NOT NULL,
    visit_type character varying(50) NOT NULL,
    department character varying(100) NOT NULL,
    doctor_name character varying(100),
    campus character varying(100),
    chief_complaint text,
    visit_status character varying(50),
    visit_summary text,
    follow_up_plan text,
    visit_date timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.visit_records OWNER TO postgres;

--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_log (id, patient_id, hospital_id, endpoint, method, action, status_code, client_ip, auth_verified, details, duration_ms, created_at) FROM stdin;
f212d910-bbbb-46f8-808a-a7eea85843f6	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/patients/fea79596-6296-4112-9b79-547826c93ebd	GET	read	200	127.0.0.1	\N	\N	15.796899795532227	2026-06-19 07:17:34.614417
1706b432-e9e8-42aa-bc66-eadcc8c133b0	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/profile	GET	read	200	127.0.0.1	\N	\N	92.86737442016602	2026-06-19 07:17:34.693665
7001df16-37fa-4c05-9ebf-e5cd1dd7d932	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	52.48117446899414	2026-06-19 07:17:34.782265
befdaf62-0da4-409e-b794-b8d02f48fcb3	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	18.66436004638672	2026-06-19 07:21:51.758729
1a08bf3f-fdcb-406b-80f6-cc8a8bed07c4	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	17.76123046875	2026-06-19 07:21:51.790984
9f9bb821-001d-4241-b05f-86848bd4e0b2	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	28.209924697875977	2026-06-19 07:21:53.774246
1f9ea93f-4394-4c1b-a4a3-d47dbabccaf4	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	29.385805130004883	2026-06-19 07:21:53.842491
f55c0be3-31c4-409c-9040-fea98c3c7ca5	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	15.767812728881836	2026-06-19 07:21:55.718291
13a70a2d-91ac-46e2-8b8b-e510b9781836	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	11.955738067626953	2026-06-19 07:21:55.744747
b1a2480e-7630-47ce-ba8b-da435cc91d10	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/patients/fea79596-6296-4112-9b79-547826c93ebd	GET	read	200	127.0.0.1	\N	\N	8.076667785644531	2026-06-19 07:26:02.922657
c90325a0-f67e-452c-a4e3-c930488f2cc3	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/profile	GET	read	200	127.0.0.1	\N	\N	20.292997360229492	2026-06-19 07:26:02.938906
95dfa60b-e16e-4c06-a988-cbb8d4988880	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	19.139528274536133	2026-06-19 07:26:02.982321
ac10e222-e2a6-45f3-9fd0-0e95c64180d9	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	24.6889591217041	2026-06-19 07:27:17.612903
8361f708-9471-40a2-b89f-024275fa9e5d	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/patients/fea79596-6296-4112-9b79-547826c93ebd	GET	read	200	127.0.0.1	\N	\N	11.038541793823242	2026-06-19 07:36:15.034714
6bfbc440-2b3a-4555-9f8a-a6a95134d03f	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/profile	GET	read	200	127.0.0.1	\N	\N	20.914554595947266	2026-06-19 07:36:15.046866
6e9d6f0c-902c-4104-be2f-168909f9519f	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	19.977807998657227	2026-06-19 07:36:15.089353
5b8dfbc3-335a-4714-830a-ed8d46c6b4b7	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/messages	GET	read	200	127.0.0.1	\N	\N	13.724327087402344	2026-06-19 07:36:16.201431
7d67a1a4-f856-48ad-b6bb-710c0351d74e	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/patients/fea79596-6296-4112-9b79-547826c93ebd	GET	read	200	127.0.0.1	\N	\N	10.72382926940918	2026-06-19 07:37:17.53416
9007ec1f-a967-4626-88bd-3c3e9290681a	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/profile	GET	read	200	127.0.0.1	\N	\N	16.816377639770508	2026-06-19 07:37:17.541388
6b1a56f4-c1e5-471f-b97d-14a079879777	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/sessions	GET	read	200	127.0.0.1	\N	\N	18.40496063232422	2026-06-19 07:37:17.586176
3c4518a8-0f10-4b3b-9cfb-19b07cc0974c	fea79596-6296-4112-9b79-547826c93ebd	\N	/api/v1/memory/conversations/messages	GET	read	200	127.0.0.1	\N	\N	11.766433715820312	2026-06-19 07:37:18.981508
\.


--
-- Data for Name: medical_records; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.medical_records (id, patient_id, hospital_id, record_type, title, department, doctor_name, chief_complaint, present_illness, diagnosis, treatment_plan, medications, notes, record_date, created_at, updated_at) FROM stdin;
c1b96060-8306-45d9-a7e1-1d751db48bcc	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	高血压复诊	心内科	王志强	晨起头晕两周，伴轻微心悸	患者高血压病史10年，长期口服缬沙坦80mg qd。近两周晨起血压偏高（150-160/90-95mmHg），伴头晕、心悸，无胸闷胸痛，无呼吸困难。自行加量至160mg后症状未缓解。	原发性高血压 2级（高危）；药物控制欠佳	1. 缬沙坦调整为160mg qd；2. 加用氨氯地平5mg qd联合降压；3. 低盐低脂饮食，每日限盐<5g；4. 家庭自测血压并记录；5. 两周后复诊评估	缬沙坦 160mg qd；氨氯地平 5mg qd	患者近期因家庭琐事情绪波动，可能影响血压控制。嘱保持情绪稳定。	2025-12-01 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
03db27e7-0bde-44f2-bf35-f51b705a58f4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	高血压常规复诊	心内科	王志强	无明显不适，常规取药复查	患者长期规律服药，家庭自测血压稳定在130-140/80-85mmHg。无头晕、胸闷等不适。	原发性高血压 2级，药物控制可	继续缬沙坦80mg qd；低盐饮食；三个月后复诊	缬沙坦 80mg qd	血压控制良好，患者依从性好。	2025-09-15 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
5ec10794-5b71-407c-8ac5-6e061296433e	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	report	年度体检报告解读	体检中心	陈建华	体检发现血脂偏高，咨询处理方案	年度体检示：总胆固醇6.2mmol/L，LDL-C 3.8mmol/L，HDL-C 1.0mmol/L。心电图：窦性心律，无明显ST-T改变。	混合型高脂血症	1. 阿托伐他汀20mg qn起始；2. 严格低脂饮食，增加膳食纤维；3. 适度有氧运动每周≥150分钟；4. 6周后复查血脂+肝功能	阿托伐他汀 20mg qn	需注意他汀类药物的肝功能监测。患者青霉素过敏，避免含青霉素类药物。	2024-06-01 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
1938925a-f2b1-4f24-b03e-dd6d039c4cd2	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	糖尿病复诊 — 血糖波动	内分泌科	李美玲	近一月空腹血糖偏高（7.5-8.5mmol/L），餐后2h血糖11-13mmol/L	2型糖尿病病史8年，口服二甲双胍500mg bid+格列美脲2mg qd。近一月饮食控制欠佳（年底聚餐增多），运动量减少。空腹血糖升至7.5-8.5mmol/L，HbA1c 7.8%。体重增加2kg。	2型糖尿病，血糖控制不良	1. 二甲双胍调整为1000mg bid；2. 格列美脲继续2mg qd；3. 严格糖尿病饮食，每日总热量控制在1600kcal；4. 每周≥5天快走30分钟；5. 每日自测空腹+睡前血糖并记录；6. 转诊营养科	二甲双胍 1000mg bid；格列美脲 2mg qd	患者对药物调整存在焦虑，已详细解释调整原因和注意事项。建议3周后复诊。	2025-11-20 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
5b673882-6610-4a1e-b46b-9924e9e414be	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	糖尿病常规复诊	内分泌科	李美玲	常规取药，无特殊不适	血糖控制可，空腹6.0-6.8mmol/L，餐后2h 8-9mmol/L。无低血糖发作。	2型糖尿病，药物控制可	继续当前方案；每三个月复查HbA1c；每年眼底+足部检查	二甲双胍 500mg bid；格列美脲 2mg qd	患者依从性好。提醒注意足部护理。	2025-06-10 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
eecca68a-5cd8-469b-9026-a43a37467c28	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	report	糖尿病并发症筛查	内分泌科	赵博	年度并发症筛查	眼底检查：轻度非增殖性糖尿病视网膜病变（双眼）。尿微量白蛋白：32mg/g Cr（轻度升高）。神经传导速度：下肢轻度感觉神经传导减慢。	糖尿病早期微血管并发症（视网膜病变I期，早期肾病）	1. 严格控制血糖（空腹<6.5mmol/L，餐后2h<8mmol/L）；2. 加用厄贝沙坦75mg qd保护肾功能；3. 每半年眼科复查；4. 低蛋白饮食（每日0.8g/kg）	二甲双胍 500mg bid；格列美脲 2mg qd；厄贝沙坦 75mg qd	患者对并发症感到担忧，已详细沟通：早期干预可延缓进展。	2024-03-05 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
64e81b71-9556-4583-841d-334bcb9e2462	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	inpatient	左膝关节置换术后住院记录	骨科	张建国	左膝全膝关节置换术后第1天	患者因左膝重度骨关节炎（Kellgren-Lawrence IV级），于2025-10-04在腰麻下行左膝全膝关节置换术（TKA）。手术顺利，术中出血约200ml。术后安返病房。	左膝重度骨关节炎，全膝关节置换术后	1. 术后24-48h预防性抗生素（头孢呋辛，已确认无头孢过敏）；2. 低分子肝素预防DVT；3. 术后第1天开始CPM机被动活动+踝泵训练；4. 术后第2天尝试下床站立；5. 疼痛管理：塞来昔布200mg bid + 按需曲马多	头孢呋辛 1.5g iv q12h（预防感染）；低分子肝素 4000IU ih qd；塞来昔布 200mg bid；曲马多 50mg prn	⚠ 磺胺类药物过敏，避免使用磺胺类及含磺胺结构药物。术后康复团队已介入。	2025-10-05 00:00:00	2026-06-18 12:31:21.780825	2026-06-18 12:31:21.780825
186ccf35-fb33-44dd-859d-3a7b9d561bff	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	outpatient	膝关节置换术后拆线复查	骨科	张建国	术后两周，伤口愈合良好，轻度肿胀	术后两周，伤口愈合良好，无红肿渗液。左膝关节活动度：屈曲0-85°，伸直0°。VAS疼痛评分2-3分（静息）/4-5分（活动时）。可拄双拐行走。	左膝TKA术后恢复期（二期愈合良好）	1. 拆线；2. 继续康复训练，目标术后6周屈曲≥110°；3. 逐渐减少拐杖依赖；4. 一月后复诊拍X光片	塞来昔布 200mg bid prn（疼痛时服用）	患者康复配合度较术后第一周有明显改善。鼓励继续坚持康复训练。	2025-10-18 00:00:00	2026-06-18 12:31:21.780825	2026-06-18 12:31:21.780825
cedc006a-3ad5-4de1-a788-c7db1e43edda	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	emergency	急诊 — 高热惊厥	儿科	刘丽华	发热39.5°C持续6小时，伴一次全身抽搐约1分钟	患儿6岁，近2天有轻微流涕、咳嗽。今日晨起突发高热，测体温39.5°C。约上午10时出现一次全身抽搐，持续约1分钟后自行缓解，意识恢复。抽搐时口吐白沫、双目上翻。既往无惊厥史。	急性上呼吸道感染；热性惊厥（单纯型）；高热	1. 物理降温+布洛芬混悬液退热（按体重计算：20mg/kg）；2. 补液：口服补液盐；3. 密切观察，若再次惊厥或持续>5分钟需紧急处理；4. 收入院观察24小时	布洛芬混悬液 100mg/5ml，每次6ml prn（q6h，体温>38.5°C时使用）	⚠ 头孢类抗生素过敏，避免使用。家长极度焦虑，已详细解释热性惊厥通常预后良好。	2025-12-05 00:00:00	2026-06-18 12:31:21.787797	2026-06-18 12:31:21.787797
612e5742-00e3-47ea-8dbc-53e7385a15e6	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	outpatient	热性惊厥后复诊	儿科	刘丽华	体温已降至正常，仍有轻咳	住院观察3天，体温逐步下降至正常范围（36.5-37.2°C），未再发生惊厥。仍有轻度干咳，精神食欲恢复。	上呼吸道感染恢复期；热性惊厥（已缓解）	1. 继续观察体温，若再次发热需及时退热；2. 小儿止咳糖浆对症处理；3. 若再次发生惊厥，需行脑电图检查；4. 一周后复诊	小儿止咳糖浆 5ml tid；布洛芬备用（仅发热时使用）	家长情绪趋于稳定。建议家中常备退热药和体温计。热性惊厥通常为良性过程，但需警惕复发。	2025-12-08 00:00:00	2026-06-18 12:31:21.787797	2026-06-18 12:31:21.787797
d7ba2a96-ca62-453f-8e79-58aea4cfae55	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	心悸待查	心内科	王志强	近一月反复心悸，伴胸闷、气短	患者近一月无明显诱因反复出现心悸，偶伴胸闷、气短，每次持续数分钟至半小时不等，休息后缓解。无胸痛、无晕厥。工作压力大，每日咖啡2-3杯。	心悸待查：功能性心律失常？焦虑状态？	1. 24小时动态心电图监测；2. 心脏彩超；3. 甲状腺功能检查；4. 减少咖啡因摄入；5. 若检查结果无异常，建议心理科咨询	暂无规律用药	⚠ 阿司匹林过敏（诱发哮喘），避免使用任何含阿司匹林及NSAIDs药物。患者工作繁忙，建议线上问诊随访。	2025-11-10 00:00:00	2026-06-18 12:31:21.794345	2026-06-18 12:31:21.794345
a8c66372-1343-4a9a-b200-b6a9c9401534	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	上腹痛伴反酸	消化内科	周明辉	反复上腹痛2月，餐后加重，伴反酸、烧心	患者近2月反复上腹部隐痛，餐后明显加重，伴反酸、胸骨后烧灼感。偶有夜间痛。进食辛辣、咖啡后加重。近一周症状加重，自行服用铝碳酸镁效果欠佳。	胃食管反流病（GERD）；慢性浅表性胃炎（待胃镜确认）	1. 奥美拉唑20mg bid餐前；2. 铝碳酸镁咀嚼片餐后+睡前prn；3. 建议行胃镜检查明确诊断；4. 饮食调整：少食多餐、避免刺激性食物、睡前3小时不进食	奥美拉唑 20mg bid（餐前30min）；铝碳酸镁 1.0g tid prn	患者因工作原因暂未做胃镜，已预约。注意与心内科就诊记录交叉关联——胸闷也可能与GERD相关。	2025-10-20 00:00:00	2026-06-18 12:31:21.794345	2026-06-18 12:31:21.794345
\.


--
-- Data for Name: memory_business_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_business_profiles (id, patient_id, hospital_id, profile_summary, risk_focus, focus_topics, care_needs, source_summary, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: memory_conversation_messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_conversation_messages (id, session_id, patient_id, hospital_id, role, content, created_at) FROM stdin;
57b2cf85-c028-4867-9dff-d908ccb04ca2	9b58578f-8ad3-4a31-8b14-461ef555827f	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	帮我查一下最近的病历记录	2026-06-18 14:52:01.597112
787e44eb-1c3c-4e44-beb7-c3b2229465ca	9b58578f-8ad3-4a31-8b14-461ef555827f	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	好的，已为您查到最近的一条病历记录。\n就诊日期：2025年11月10日 \n科室：心内科（上海某院区） \n医生：王志强 \n主诉：近一个月反复心悸，伴胸闷、气短。 \n现病史：无明显诱因反复出现心悸，偶伴胸闷、气短，每次持续数分钟至半小时，休息后可缓解。无胸痛、无晕厥。工作压力大，每天喝咖啡2-3杯。 \n诊断：心悸待查——功能性心律失常？焦虑状态？ \n检查与治疗计划： \n建议做24小时动态心电图监测 \n心脏彩超 \n甲状腺功能检查 \n减少咖啡因摄入 \n若以上检查结果无异常，建议心理科咨询 \n用药情况：目前暂未规律用药。 \n病历特别备注：⚠ 您对阿司匹林过敏（曾诱发哮喘），病历中已明确避免使用任何含阿司匹林及非甾体抗炎药（NSAIDs）的药物。就诊时务必提醒医生此过敏史。 \n个人信息备注：您2025年时工作繁忙，偏好线上问诊，职业为金融分析师。 \n如果您想了解这份记录中的具体检查结果（如动态心电图报告等），或需要我帮您查找其他更早的病史，请告诉我。但请注意，我不能代替医生做诊断或开药，所有治疗调整请与您的专科医生沟通。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 阿司匹林。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-18 14:52:01.617826
27587df9-d947-4b97-826f-44e29afe7e99	ebe35f8c-88df-40a7-9180-b9dbdb4ffa6a	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	帮我查一下最近的病历记录	2026-06-18 14:57:02.462019
9403bdb2-0c92-43c1-a4cc-fe9d8e5c9409	ebe35f8c-88df-40a7-9180-b9dbdb4ffa6a	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	根据您最近的病历记录（2025年11月10日，心内科门诊），主要情况如下：\n诊断：心悸待查，考虑可能是功能性心律失常或焦虑状态。\n主要症状：近一个月无明显诱因反复出现心悸，偶尔伴有胸闷、气短，每次持续几分钟到半小时，休息后能缓解，没有胸痛或晕厥。您目前工作压力较大，每天喝2-3杯咖啡。\n治疗计划：\n 1. 做24小时动态心电图。\n 2. 做心脏彩超。\n 3. 检查甲状腺功能。\n 4. 减少咖啡因摄入。\n 5. 如果检查结果没有异常，建议去心理科咨询。\n用药：目前没有规律用药。\n重要提醒：您有阿司匹林过敏（曾诱发哮喘），记录中已明确提醒避免使用任何含阿司匹林或NSAIDs（非甾体抗炎药）的药物。\n如果您需要更早的记录或更详细的信息，目前查询到的只有这一条，您可以进一步说明需求。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 阿司匹林。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-18 14:57:02.478586
d19f800f-9c5e-4f28-b662-2d2ff5026e9c	11d41de2-b12a-4288-8c62-cbdd2bec579c	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 02:35:33.894101
02b41378-07e3-4f01-a23e-8ddb7665d066	11d41de2-b12a-4288-8c62-cbdd2bec579c	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有以下药物过敏信息：\n青霉素过敏：曾出现皮疹反应。\n头孢类药物慎用：因既往有过轻度皮疹。\n此外，在您的一份体检报告处理意见中也特别备注了“患者青霉素过敏，避免含青霉素类药物”。这些信息非常重要，在您未来就诊或用药时，务必主动告知医生。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 02:35:33.924663
0b4d2314-ccd4-4928-ab1f-6a858df1ac18	e74e2a5f-e7d9-4cd4-9dc6-230caa302b38	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	user	我的紧急联系人是谁？	2026-06-19 02:35:45.380241
12e9af2c-86da-4db5-909c-72faa852d762	e74e2a5f-e7d9-4cd4-9dc6-230caa302b38	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	assistant	根据您的档案信息，您的紧急联系人是：张芳（女儿），联系电话：13700030002。	2026-06-19 02:35:45.392746
198a5e73-c12d-4de9-8b34-59749b2d0c9e	2f490345-aef7-4044-8f6d-aeba38756c14	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我最近一次看病的医生是谁？	2026-06-19 02:35:50.708849
9f38bf7a-ee73-4b1b-a9d7-408cff260ee1	2f490345-aef7-4044-8f6d-aeba38756c14	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	您最近一次看病是在 2025年12月1日，就诊科室是 心内科，接诊医生是 王志强 医生。	2026-06-19 02:35:50.716876
45ca9104-478d-43aa-badb-641d751399bd	4c28063b-21b9-4ac8-a24a-ca7cea185db4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 07:15:36.259918
57a1fc76-9307-4e49-9c52-780ce9a380e4	4c28063b-21b9-4ac8-a24a-ca7cea185db4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有以下药物过敏信息：\n青霉素过敏：曾出现过皮疹。\n头孢类药物需慎用：既往有过轻度皮疹反应。\n请注意，在使用任何新药物前，都应告知医生您的过敏史。如果您对当前的治疗方案有疑问，请咨询您的医生或药师。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:15:36.290958
f90dafa5-17a6-489a-a732-27b7edeac170	f1f99f50-81e3-43db-90c0-bfa4033170b1	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 07:16:37.286413
e77cbcf4-4ab9-4350-82fd-b05d6e4a3969	f1f99f50-81e3-43db-90c0-bfa4033170b1	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的档案记录，您有以下药物过敏信息：\n青霉素类：过敏（曾出现皮疹）。\n头孢类：需慎用（您既往有轻度皮疹史）。\n请注意，在您之前的血脂治疗记录中也特别备注了“患者青霉素过敏，避免含青霉素类药物”。今后就医或用药时，请务必告知医生您有这些过敏史。\n如果您需要了解更具体的细节（比如过敏当时的情况或严重程度），现有资料中信息不够充分，建议咨询您的主治医生或查阅更详细的过敏检测报告。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:16:37.303215
5a0397d3-21a6-453a-ad0e-85f53e800d8b	11166174-a144-465b-8769-f85cb18d1147	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 07:17:02.9974
48e0b7a2-4c29-47c1-9079-6e80f7ee9d27	2e6ffee4-25cf-4f5a-9513-db439dbdc845	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	根据我的情况给一些健康建议	2026-06-19 07:17:59.019421
24badc01-2300-4771-a3fc-b858668ddabd	11166174-a144-465b-8769-f85cb18d1147	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的医疗记录，您有明确的药物过敏史：对青霉素过敏（曾出现过皮疹）。另外，头孢类药物也属于慎用范围（因既往有过轻度皮疹反应）。 \n请务必牢记，在就诊或用药时主动告知医生这一情况，以避免使用含青霉素或可能交叉过敏的药物。 \n（注意：以上信息来自您的病历记录，具体用药方案请以医生当面评估为准。）\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:17:03.008476
641d4630-7906-4cce-8e08-92aaefd13ad5	2e6ffee4-25cf-4f5a-9513-db439dbdc845	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	好的，文婷，根据你最近的就诊记录和整体情况，我为你梳理了以下几条重点健康建议。\n\n**核心结论：** 你目前的核心问题是**胃食管反流（GERD）** 和**原因待查的心悸**，两者可能相互影响，且与你的工作压力（金融分析师）高度相关。建议你优先按医嘱完成检查，同时从**饮食、压力管理和睡眠**三个维度进行生活调整。\n\n### 1. 关于消化系统（GERD + 慢性胃炎）\n\n- **用药安全提醒：** 你正在服用**奥美拉唑**（PPI）和**铝碳酸镁**。请务必按时按量服用，特别是奥美拉唑要在餐前服用。你的过敏史中没有提到这类药物，目前方案是安全的。但**请不要自行加用任何止痛药或感冒药**，尤其要警惕含有**布洛芬、萘普生、双氯芬酸**等非甾体抗炎药（NSAIDs）的药物，因为它们和**阿司匹林**属于同类，同样会刺激胃黏膜，加重你的胃病。\n- **饮食调整（核心）：**\n    - **少食多餐**：将三餐分成五到六小餐，避免过饱。\n    - **绝对避免**：咖啡、浓茶、巧克力、碳酸饮料、辛辣油炸食物、过甜的食物（如蛋糕、奶茶）。这些都会直接诱发反流和心悸。\n    - **睡前习惯**：睡前3小时内**绝对不要进食**，包括喝水。睡觉时可以稍微垫高床头。\n- **胃镜检查建议：** 你已经预约了胃镜，请务必完成。这是明确诊断慢性胃炎和排除其他问题的金标准，不要因为工作忙而推迟。\n\n### 2. 关于心脏问题（心悸待查）\n\n- **积极配合检查：** 你正在做**24小时动态心电图**和**心脏彩超**，这是排查心律失常和心脏结构问题的关键。另外，医生还建议了**甲状腺功能检查**，请务必加上。因为甲状腺功能异常（甲亢、甲减）都会引起心悸，而你母亲有甲减病史，这一点对你很重要。\n- **咖啡因管理：** 医生明确建议减少咖啡因摄入。作为金融分析师，咖啡可能是你的日常伴侣，但它是心悸和反流的共同诱因。**请尝试用低因咖啡或草本茶（如洋甘菊茶）替代**，并记录两周内的心悸发作频率有无改善。\n- **压力与情绪：** 功能性心律失常和焦虑状态高度相关。你的工作节奏快、压力大，这是重要的诱发因素。建议：\n    - **正念呼吸练习**：每天花5-10分钟，专注呼吸，能快速调节心率。\n    - **定时起立活动**：每工作45分钟，站起来走动2分钟，做几个深呼吸，能有效缓解紧张。\n\n### 3. 综合生活方式建议\n\n- **运动：** 避免剧烈运动（如高强度间歇训练），以免诱发心悸。推荐**散步、瑜伽、游泳**等舒缓运动。每次30分钟，每周至少3次。运动后注意补充水分。\n- **睡眠：** 尽量保证每晚7-8小时睡眠。如果因压力失眠，睡前1小时远离手机和电脑，可以尝试听白噪音或做拉伸。\n- **复诊跟踪：** 你下周需要带结果去**心内科复诊（王医生）**，两周后也要去**消化内科复诊（周医生，带胃镜结果）**。请务必按时去。如果心悸加重，伴随胸痛、头晕或眼前发黑，请立即去急诊。\n\n### 特别提醒（过敏史相关）\n\n你已知对**阿司匹林**（诱发哮喘）和**花粉**过敏。未来如果需要任何治疗（如关节炎、感冒发烧、疼痛等），**必须明确告知医生你的阿司匹林过敏史和哮喘病史**。医生会为你选择安全的替代药物（如对乙酰氨基酚等）。\n\n总结：你目前的健康问题属于典型的“身心疾病”，消化和心脏的症状都与中枢神经系统（压力、焦虑）密切相关。**先依赖检查排除器质性病变，再通过生活方式干预解决功能性问题**，这是最适合你的路径。祝你早日康复！\n\n---\n⚠️ **安全提醒**：系统检测到回答中提到了 **阿司匹林、花粉**。根据患者档案，患者对该药物**已知过敏**。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:17:59.029469
15ea8efb-212e-4894-a5f7-5c63afa52bc9	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	上次就诊的诊断结果	2026-06-19 07:26:30.344938
9636fa13-2e8a-4655-8e14-f3d6798d8619	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	你是谁呢？	2026-06-19 07:37:03.447362
b50eb8e5-3aae-4578-b0f7-7eb2c41969fd	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	根据您最近的医疗记录，您最近一次就诊（2025年11月10日，心内科）的诊断结果是：心悸待查，医生初步考虑可能与 功能性心律失常 或 焦虑状态 有关。\n目前诊断还未完全明确，因为医生当时为您开具了 24小时动态心电图 和 心脏彩超 检查，这些检查结果是否已经回报、结果如何，现有信息中并未记录。因此，尚不清楚最终的明确诊断是什么。\n另外，需要提醒您注意几点：\n检查结果：您上次就诊后是否已完成动态心电图和心脏彩超？如果已完成，建议带着结果尽快复诊（原计划是一周后携带结果复诊）。\n症状监测：如果心悸、胸闷症状加重，或出现胸痛、晕厥等新情况，请及时去急诊。\n饮食与作息：医生建议减少咖啡因摄入（您当时每天喝2-3杯咖啡），同时您因工作压力大，建议适当调整作息、管理情绪。\n过敏提醒：您对阿司匹林过敏（会诱发哮喘），所有含阿司匹林或同类药物（如布洛芬等非甾体抗炎药）都应严格避免。\n此外，您在2025年10月20日消化内科的就诊诊断是：胃食管反流病（GERD） 和可能的 慢性浅表性胃炎（待胃镜确认），当时已开始服用奥美拉唑治疗，并且预约了胃镜。这部分情况也请继续按消化科医生的方案随访。\n如果您是需要我回顾更早之前（比如首次消化内科就诊）的诊断详情，请告诉我，我可以继续为您提供。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 阿司匹林。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:26:30.350378
a372b889-6a03-4422-b5d8-1a21dd39df29	9984be28-353e-4562-b830-bae32d3c876a	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 07:27:18.815743
68ee17b2-12ee-483c-99ac-c9ce2dff9808	9984be28-353e-4562-b830-bae32d3c876a	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您对青霉素过敏（曾有皮疹反应）。此外，病历中还提示头孢类药物需慎用，因为您既往有轻度皮疹史。 \n与医生沟通或开药时，请务必主动告知上述过敏情况。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 07:27:18.823955
fcbb4467-b60e-4e45-bc4e-daf4c962bea1	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	我是您的中国医疗助手，可以记住您之前的对话和健康信息。我将尽力为您提供专业、安全的医疗相关建议，但请注意我不能代替医生做最终诊断或开药。有什么健康方面的问题，随时可以问我。	2026-06-19 07:37:03.458198
089103e4-93d4-4e59-b3db-4af64bb9faeb	3ae9c7ad-0e65-4ebd-b778-c64eb570d2dd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 13:47:46.965206
ed499a85-cc72-4b6a-8127-f519cd312009	3ae9c7ad-0e65-4ebd-b778-c64eb570d2dd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有明确的药物过敏史：对青霉素过敏（曾出现皮疹），并且头孢类药物需要慎用（既往有轻度皮疹记录）。其他药物目前未见过敏记录。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 13:47:46.98315
50ab4e70-9a76-4dd5-8ee6-fe86f1c7da10	1ac4c2df-4a85-4cc1-a63f-ecb3059ea4fb	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 13:51:28.332936
75cf3919-6f0a-4bf5-a0cd-f08615336e63	1ac4c2df-4a85-4cc1-a63f-ecb3059ea4fb	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有以下药物过敏史：\n青霉素类：您对青霉素过敏，曾出现过皮疹。\n头孢菌素类：医生注明需慎用，因为既往有过轻度皮疹。\n请您务必在就诊和用药时，主动告知医生和药师以上过敏信息。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 13:51:28.345327
8e42af6f-02ce-4421-a809-c788fd2ce07a	3cb6d386-c40a-402e-bb72-ffb999556a05	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 13:52:22.534465
3b64f2dd-c29b-4978-9295-2b2f277fcf85	3cb6d386-c40a-402e-bb72-ffb999556a05	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有以下药物过敏信息：\n青霉素过敏：曾出现过皮疹。\n头孢类抗生素需慎用：既往有过轻度皮疹。\n因此，您在就诊时务必主动告知医生这些过敏情况，特别是当医生考虑使用抗生素时。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 13:52:22.544044
1c038b02-0db5-41e9-bb34-4288fed54c86	0b9534c6-d9d0-487e-85c3-f69e1aa0afba	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 13:57:03.748923
759fbb83-bb87-49c0-93eb-a1c08481305f	0b9534c6-d9d0-487e-85c3-f69e1aa0afba	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的健康档案记录，您对青霉素过敏（曾有皮疹反应），同时头孢类药物也需要慎重使用（既往有过轻度皮疹）。用药时请注意告知医生这些情况，具体哪些药不能用、能否换用其他药，需要由医生结合您的实际病情来判断。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 13:57:03.761169
dccca7b5-7ece-4329-b23d-cc282c6bb921	e17177ad-9a98-4677-a720-fa9dc232d6fd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	我有什么药物过敏吗？	2026-06-19 14:19:53.892611
7f545765-cedc-41c8-b092-2961dd80ab48	e17177ad-9a98-4677-a720-fa9dc232d6fd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	根据您的病历记录，您有以下药物过敏信息：对青霉素过敏（曾出现皮疹），另外头孢类抗生素需要慎用（既往有轻度皮疹史）。请您在就医或用药时务必告知医生这些情况，避免使用相关药物。\n---\n⚠️ 安全提醒：系统检测到回答中提到了 青霉素。根据患者档案，患者对该药物已知过敏。请在用药前务必确认患者的过敏史，避免使用过敏药物。	2026-06-19 14:19:53.913351
\.


--
-- Data for Name: memory_conversation_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_conversation_profiles (id, patient_id, hospital_id, profile_summary, communication_preference, focus_topics, source_summary, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: memory_key_events_v2; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_key_events_v2 (id, patient_id, hospital_id, type, content, impact, confidence, source_type, source_ref, evidence, canonical_key, status, priority, tags, event_time, last_confirmed_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: memory_knowledge_chunks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_knowledge_chunks (id, hospital_id, domain, title, chunk_text, source_type, source_ref, version, confidence, tags, embedding_key, effective_from, expires_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: memory_preferences; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_preferences (id, patient_id, hospital_id, answer_style, answer_length, tone_style, medical_term_level, risk_alert_level, preferred_language, prefer_summary_first, prefer_step_by_step, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: memory_session_buffer_messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_session_buffer_messages (id, session_id, hospital_id, role, content, created_at) FROM stdin;
0824dacc-c921-4305-bb05-3215f5d9698c	b544a617-8863-4f92-85b7-c4b4de121321	\N	user	你好	2026-06-18 07:07:12.109156
5776fb17-18f4-455a-a4d3-7aa0e5885dcc	b544a617-8863-4f92-85b7-c4b4de121321	\N	assistant	你好！我是你的健康助理，有什么可以帮你的吗？如果有任何身体不适或健康方面的疑问，都可以告诉我。我会尽力为你提供专业的分析和建议。	2026-06-18 07:07:12.151313
ec349ec9-9538-4f5e-a3ec-1cffbcc0feaa	aee61297-af16-4156-8a72-454ab1fd4c1e	\N	user	你好呀你是谁	2026-06-18 11:26:50.490683
ad88e091-b941-47c0-9d2e-f0b57448db90	aee61297-af16-4156-8a72-454ab1fd4c1e	\N	assistant	你好呀！我是小善，你的中文医疗助手，专门帮你解答健康相关的疑问、提供医学知识和日常保健建议的。我不是真正的医生，不能做诊断或开药，但我会尽最大努力给你提供靠谱、安全的信息。有什么问题尽管问我吧，咱们慢慢聊～	2026-06-18 11:26:50.540787
9d1211d6-afb8-45de-a00d-eeffde1fab4c	56fa4f24-39a8-4635-9b02-87dbbefbc5c1	\N	user	你好	2026-06-18 13:28:16.228095
440f42b3-91bb-417c-9bef-be7fa7875c4f	56fa4f24-39a8-4635-9b02-87dbbefbc5c1	\N	assistant	你好！我是你的智能健康助手，有什么身体不适或健康方面的问题可以随时告诉我。为了能更准确地帮你分析，可以先告诉我你的年龄、性别，以及有没有药物过敏史吗？这样我会更谨慎地给出建议。	2026-06-18 13:28:16.274082
\.


--
-- Data for Name: memory_user_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.memory_user_profiles (id, patient_id, hospital_id, profile_summary, communication_preference, risk_focus, focus_topics, care_needs, source_summary, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: patients; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.patients (id, hospital_id, patient_code, full_name, gender, birth_date, phone, id_number_hash, id_number_last4, address, emergency_contact_name, emergency_contact_phone, blood_type, allergy_history, family_history, notes, is_active, created_at, updated_at) FROM stdin;
3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	P0002	林美娟	female	1975-08-22	13900020001	\N	\N	上海市徐汇区漕河泾开发区田林路200号502室	林志强（儿子）	13900020002	O	无已知药物过敏	母亲：2型糖尿病、高血压；父亲：体健；有糖尿病家族聚集倾向	对用药调整较焦虑，需要耐心解释；职业：公司财务	t	2026-06-18 12:31:21.75667	2026-06-18 12:31:21.75667
8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	P0003	张国栋	male	1955-03-15	13700030001	\N	\N	北京市朝阳区望京街道花家地北里5号楼3单元102	张芳（女儿）	13700030002	B	磺胺类药物过敏（全身皮疹+发热）；酒精过敏（面部潮红）	父亲：骨关节炎、高血压；母亲：体健	需要轮椅辅助；术后康复训练配合度一般，需要多鼓励；职业：退休工人	t	2026-06-18 12:31:21.770251	2026-06-18 12:31:21.770251
3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	P0004	吴小雅	female	2019-11-28	13600040001	\N	\N	上海市闵行区莘庄镇莘建路100号601室	吴建国（父亲）	13600040002	AB	头孢类抗生素过敏（既往注射头孢曲松后出现荨麻疹）	父亲：过敏性鼻炎；母亲：体健；无明确遗传病史	家长焦虑程度较高，就诊时需额外安抚；需注意用药剂量按体重计算	t	2026-06-18 12:31:21.778836	2026-06-18 12:31:21.778836
fea79596-6296-4112-9b79-547826c93ebd	hospital-b	P1001	郑文婷	female	1982-07-03	13500050001	\N	\N	上海市静安区南京西路1266号恒隆广场附近	郑磊（哥哥）	13500050002	A	阿司匹林过敏（诱发哮喘）；花粉过敏（季节性）	父亲：高血压、胃溃疡；母亲：甲状腺功能减退	工作繁忙，偏好线上问诊；跨院区就诊（hospital-a心内科，hospital-b消化科）；职业：金融分析师	t	2026-06-18 12:31:21.785564	2026-06-18 12:31:21.785564
e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	P0001	陈建国	male	1968-05-10	13800010001	\N	\N	上海市浦东新区张江镇碧波路888弄12号301室	陈梅（配偶）	13800010002	A	青霉素过敏（皮疹）；头孢类慎用（既往轻度皮疹）	父亲：高血压、冠心病，68岁心梗去世；母亲：高血压，健在	test update OK	t	2026-06-18 12:31:21.752354	2026-06-18 15:18:27.668473
\.


--
-- Data for Name: visit_records; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.visit_records (id, patient_id, hospital_id, visit_type, department, doctor_name, campus, chief_complaint, visit_status, visit_summary, follow_up_plan, visit_date, created_at, updated_at) FROM stdin;
33938f3f-5336-4c73-95ec-cd1497c6971b	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	心内科	王志强	本部院区	晨起头晕两周，伴轻微心悸	completed	血压控制欠佳，调整降压方案：缬沙坦加量+加用氨氯地平。嘱低盐饮食、家庭血压监测。两周后复诊。	两周后复诊心内科，复查血压+心电图。同步复查血脂（上次体检血脂偏高）。	2025-12-01 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
339612e0-c551-40ce-b944-ad7ce258d8ea	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	心内科	王志强	本部院区	常规取药复查	completed	血压控制良好，继续当前方案。常规取药缬沙坦3个月用量。	三个月后复诊取药。	2025-09-15 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
c129ba4b-824c-425f-b841-d7ad5662ace3	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	体检中心	陈建华	本部院区	年度体检报告解读	completed	体检示高脂血症，给予阿托伐他汀治疗。建议生活方式干预。	6周后复查血脂+肝功能。	2024-06-01 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
b681a4a2-4890-461a-b5a3-f2c974429d15	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	内分泌科	李美玲	本部院区	血糖波动，餐后偏高	completed	血糖控制不良，调整二甲双胍剂量。转诊营养科进行饮食指导。患者对药物调整存在焦虑，已详细解释。	三周后复诊内分泌科，空腹+餐后2h血糖+HbA1c。同步营养科门诊。	2025-11-20 00:00:00	2026-06-18 12:31:21.776276	2026-06-18 12:31:21.776276
dbcf202b-ebe4-462e-8a36-2e15a269bc43	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	follow_up	内分泌科	李美玲	本部院区	常规取药，无特殊不适	completed	血糖控制可，常规取药。提醒足部护理和年度眼底检查。	每三个月复诊取药。今年内完成眼底检查。	2025-06-10 00:00:00	2026-06-18 12:31:21.776276	2026-06-18 12:31:21.776276
a84fb6b2-7653-48ff-9c72-82b6c1c7f6cf	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	inpatient	骨科	张建国	本部院区	左膝重度骨关节炎，入院行关节置换术	admitted	入院行左膝全膝关节置换术。术前评估：心肺功能可，手术风险可控。注意磺胺过敏史。	术后2周拆线复查；术后6周X光片+功能评估；术后3/6/12月定期复查。	2025-10-04 00:00:00	2026-06-18 12:31:21.782539	2026-06-18 12:31:21.782539
4e8e6820-2437-48cd-8606-c588ae32fdfe	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	follow_up	骨科	张建国	本部院区	关节置换术后2周拆线+复查	completed	伤口愈合良好，拆线。关节活动度可（屈曲0-85°）。继续康复训练，鼓励增加活动量。	一月后拍X光片复查。康复科继续随访。	2025-10-18 00:00:00	2026-06-18 12:31:21.782539	2026-06-18 12:31:21.782539
e3ad33ec-be5f-470c-b0d3-e5f45936febb	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	emergency	儿科	刘丽华	本部院区	高热39.5°C，抽搐一次	admitted	急性上呼吸道感染合并热性惊厥。给予退热、补液处理，收入院观察。家长焦虑，已安抚并详细解释病情。	住院观察3天，稳定后出院。出院3天后复诊。若再次惊厥需行脑电图。	2025-12-05 00:00:00	2026-06-18 12:31:21.790809	2026-06-18 12:31:21.790809
4f82b3f7-a8cc-4aec-826e-a85ed0558413	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	follow_up	儿科	刘丽华	本部院区	热退，轻咳，复诊评估	completed	体温正常，未再惊厥。精神食欲恢复，轻咳对症处理。家长情绪稳定。	一周后复诊。家中常备退热药。若发热需及时退热处理，警惕惊厥复发。	2025-12-08 00:00:00	2026-06-18 12:31:21.790809	2026-06-18 12:31:21.790809
f9cffd3b-2697-4776-9728-7724e324e386	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	心内科	王志强	本部院区	反复心悸、胸闷	completed	心悸待查，已开具动态心电图和心脏彩超，待结果回报。建议减少咖啡因摄入。	一周后携带检查结果复诊心内科。若心悸加重随时急诊。	2025-11-10 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
7c0d09d2-f23c-427b-bb1f-eac670c5529d	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	消化内科	周明辉	东院区	上腹痛、反酸、烧心	completed	诊断GERD+慢性胃炎可能，启动PPI治疗。胃镜已预约，待检查明确诊断。	两周后消化内科复诊（携带胃镜结果）。药效评估后决定是否调整方案。	2025-10-20 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
1428212a-83af-495f-9c35-ef9f19777041	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	消化内科	周明辉	东院区	偶尔反酸，首次就诊	completed	症状较轻，建议生活方式调整：少食多餐、避免刺激性食物。暂不用药观察。	若症状持续或加重则复诊。	2025-09-01 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
\.


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: medical_records medical_records_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_pkey PRIMARY KEY (id);


--
-- Name: memory_business_profiles memory_business_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_business_profiles
    ADD CONSTRAINT memory_business_profiles_pkey PRIMARY KEY (id);


--
-- Name: memory_conversation_messages memory_conversation_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_conversation_messages
    ADD CONSTRAINT memory_conversation_messages_pkey PRIMARY KEY (id);


--
-- Name: memory_conversation_profiles memory_conversation_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_conversation_profiles
    ADD CONSTRAINT memory_conversation_profiles_pkey PRIMARY KEY (id);


--
-- Name: memory_key_events_v2 memory_key_events_v2_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_key_events_v2
    ADD CONSTRAINT memory_key_events_v2_pkey PRIMARY KEY (id);


--
-- Name: memory_knowledge_chunks memory_knowledge_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_knowledge_chunks
    ADD CONSTRAINT memory_knowledge_chunks_pkey PRIMARY KEY (id);


--
-- Name: memory_preferences memory_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_preferences
    ADD CONSTRAINT memory_preferences_pkey PRIMARY KEY (id);


--
-- Name: memory_session_buffer_messages memory_session_buffer_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_session_buffer_messages
    ADD CONSTRAINT memory_session_buffer_messages_pkey PRIMARY KEY (id);


--
-- Name: memory_user_profiles memory_user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_user_profiles
    ADD CONSTRAINT memory_user_profiles_pkey PRIMARY KEY (id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: patients uq_patient_hospital_code; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT uq_patient_hospital_code UNIQUE (hospital_id, patient_code);


--
-- Name: visit_records visit_records_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.visit_records
    ADD CONSTRAINT visit_records_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_audit_log_action ON public.audit_log USING btree (action);


--
-- Name: ix_audit_log_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_audit_log_patient_id ON public.audit_log USING btree (patient_id);


--
-- Name: ix_medical_records_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_medical_records_hospital_id ON public.medical_records USING btree (hospital_id);


--
-- Name: ix_medical_records_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_medical_records_patient_id ON public.medical_records USING btree (patient_id);


--
-- Name: ix_medical_records_record_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_medical_records_record_date ON public.medical_records USING btree (record_date);


--
-- Name: ix_medical_records_record_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_medical_records_record_type ON public.medical_records USING btree (record_type);


--
-- Name: ix_memory_business_profiles_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_business_profiles_hospital_id ON public.memory_business_profiles USING btree (hospital_id);


--
-- Name: ix_memory_business_profiles_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_memory_business_profiles_patient_id ON public.memory_business_profiles USING btree (patient_id);


--
-- Name: ix_memory_conversation_messages_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_conversation_messages_hospital_id ON public.memory_conversation_messages USING btree (hospital_id);


--
-- Name: ix_memory_conversation_messages_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_conversation_messages_patient_id ON public.memory_conversation_messages USING btree (patient_id);


--
-- Name: ix_memory_conversation_messages_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_conversation_messages_session_id ON public.memory_conversation_messages USING btree (session_id);


--
-- Name: ix_memory_conversation_profiles_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_conversation_profiles_hospital_id ON public.memory_conversation_profiles USING btree (hospital_id);


--
-- Name: ix_memory_conversation_profiles_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_memory_conversation_profiles_patient_id ON public.memory_conversation_profiles USING btree (patient_id);


--
-- Name: ix_memory_key_events_v2_canonical_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_canonical_key ON public.memory_key_events_v2 USING btree (canonical_key);


--
-- Name: ix_memory_key_events_v2_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_hospital_id ON public.memory_key_events_v2 USING btree (hospital_id);


--
-- Name: ix_memory_key_events_v2_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_patient_id ON public.memory_key_events_v2 USING btree (patient_id);


--
-- Name: ix_memory_key_events_v2_source_ref; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_source_ref ON public.memory_key_events_v2 USING btree (source_ref);


--
-- Name: ix_memory_key_events_v2_source_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_source_type ON public.memory_key_events_v2 USING btree (source_type);


--
-- Name: ix_memory_key_events_v2_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_status ON public.memory_key_events_v2 USING btree (status);


--
-- Name: ix_memory_key_events_v2_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_key_events_v2_type ON public.memory_key_events_v2 USING btree (type);


--
-- Name: ix_memory_knowledge_chunks_domain; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_knowledge_chunks_domain ON public.memory_knowledge_chunks USING btree (domain);


--
-- Name: ix_memory_knowledge_chunks_embedding_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_knowledge_chunks_embedding_key ON public.memory_knowledge_chunks USING btree (embedding_key);


--
-- Name: ix_memory_knowledge_chunks_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_knowledge_chunks_hospital_id ON public.memory_knowledge_chunks USING btree (hospital_id);


--
-- Name: ix_memory_knowledge_chunks_source_ref; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_knowledge_chunks_source_ref ON public.memory_knowledge_chunks USING btree (source_ref);


--
-- Name: ix_memory_knowledge_chunks_source_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_knowledge_chunks_source_type ON public.memory_knowledge_chunks USING btree (source_type);


--
-- Name: ix_memory_preferences_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_preferences_hospital_id ON public.memory_preferences USING btree (hospital_id);


--
-- Name: ix_memory_preferences_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_memory_preferences_patient_id ON public.memory_preferences USING btree (patient_id);


--
-- Name: ix_memory_session_buffer_messages_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_session_buffer_messages_hospital_id ON public.memory_session_buffer_messages USING btree (hospital_id);


--
-- Name: ix_memory_session_buffer_messages_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_session_buffer_messages_session_id ON public.memory_session_buffer_messages USING btree (session_id);


--
-- Name: ix_memory_user_profiles_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_user_profiles_hospital_id ON public.memory_user_profiles USING btree (hospital_id);


--
-- Name: ix_memory_user_profiles_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_memory_user_profiles_patient_id ON public.memory_user_profiles USING btree (patient_id);


--
-- Name: ix_patients_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_patients_hospital_id ON public.patients USING btree (hospital_id);


--
-- Name: ix_patients_id_number_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_patients_id_number_hash ON public.patients USING btree (id_number_hash);


--
-- Name: ix_patients_patient_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_patients_patient_code ON public.patients USING btree (patient_code);


--
-- Name: ix_patients_phone; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_patients_phone ON public.patients USING btree (phone);


--
-- Name: ix_visit_records_hospital_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_visit_records_hospital_id ON public.visit_records USING btree (hospital_id);


--
-- Name: ix_visit_records_patient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_visit_records_patient_id ON public.visit_records USING btree (patient_id);


--
-- Name: ix_visit_records_visit_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_visit_records_visit_date ON public.visit_records USING btree (visit_date);


--
-- Name: ix_visit_records_visit_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_visit_records_visit_type ON public.visit_records USING btree (visit_type);


--
-- Name: medical_records medical_records_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.medical_records
    ADD CONSTRAINT medical_records_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id);


--
-- Name: visit_records visit_records_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.visit_records
    ADD CONSTRAINT visit_records_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id);


--
-- PostgreSQL database dump complete
--

\unrestrict pnle0J2c7SVUvA06TEqYXK8gRLDVQnMwC7EkJ6zP7KoIG5HjenxJxV4jWDWjPSM

