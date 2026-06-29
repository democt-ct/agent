--
-- PostgreSQL database dump
--


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
c1b96060-8306-45d9-a7e1-1d751db48bcc	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	楂樿鍘嬪璇?蹇冨唴绉?鐜嬪織寮?鏅ㄨ捣澶存檿涓ゅ懆锛屼即杞诲井蹇冩偢	鎮ｈ€呴珮琛€鍘嬬梾鍙?0骞达紝闀挎湡鍙ｆ湇缂矙鍧?0mg qd銆傝繎涓ゅ懆鏅ㄨ捣琛€鍘嬪亸楂橈紙150-160/90-95mmHg锛夛紝浼村ご鏅曘€佸績鎮革紝鏃犺兏闂疯兏鐥涳紝鏃犲懠鍚稿洶闅俱€傝嚜琛屽姞閲忚嚦160mg鍚庣棁鐘舵湭缂撹В銆?鍘熷彂鎬ч珮琛€鍘?2绾э紙楂樺嵄锛夛紱鑽墿鎺у埗娆犱匠	1. 缂矙鍧﹁皟鏁翠负160mg qd锛?. 鍔犵敤姘ㄦ隘鍦板钩5mg qd鑱斿悎闄嶅帇锛?. 浣庣洂浣庤剛楗锛屾瘡鏃ラ檺鐩?5g锛?. 瀹跺涵鑷祴琛€鍘嬪苟璁板綍锛?. 涓ゅ懆鍚庡璇婅瘎浼?缂矙鍧?160mg qd锛涙皑姘湴骞?5mg qd	鎮ｈ€呰繎鏈熷洜瀹跺涵鐞愪簨鎯呯华娉㈠姩锛屽彲鑳藉奖鍝嶈鍘嬫帶鍒躲€傚槺淇濇寔鎯呯华绋冲畾銆?2025-12-01 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
03db27e7-0bde-44f2-bf35-f51b705a58f4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	楂樿鍘嬪父瑙勫璇?蹇冨唴绉?鐜嬪織寮?鏃犳槑鏄句笉閫傦紝甯歌鍙栬嵂澶嶆煡	鎮ｈ€呴暱鏈熻寰嬫湇鑽紝瀹跺涵鑷祴琛€鍘嬬ǔ瀹氬湪130-140/80-85mmHg銆傛棤澶存檿銆佽兏闂风瓑涓嶉€傘€?鍘熷彂鎬ч珮琛€鍘?2绾э紝鑽墿鎺у埗鍙?缁х画缂矙鍧?0mg qd锛涗綆鐩愰ギ椋燂紱涓変釜鏈堝悗澶嶈瘖	缂矙鍧?80mg qd	琛€鍘嬫帶鍒惰壇濂斤紝鎮ｈ€呬緷浠庢€уソ銆?2025-09-15 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
5ec10794-5b71-407c-8ac5-6e061296433e	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	report	骞村害浣撴鎶ュ憡瑙ｈ	浣撴涓績	闄堝缓鍗?浣撴鍙戠幇琛€鑴傚亸楂橈紝鍜ㄨ澶勭悊鏂规	骞村害浣撴绀猴細鎬昏儐鍥洪唶6.2mmol/L锛孡DL-C 3.8mmol/L锛孒DL-C 1.0mmol/L銆傚績鐢靛浘锛氱鎬у績寰嬶紝鏃犳槑鏄維T-T鏀瑰彉銆?娣峰悎鍨嬮珮鑴傝鐥?1. 闃挎墭浼愪粬姹€20mg qn璧峰锛?. 涓ユ牸浣庤剛楗锛屽鍔犺喅椋熺氦缁达紱3. 閫傚害鏈夋哀杩愬姩姣忓懆鈮?50鍒嗛挓锛?. 6鍛ㄥ悗澶嶆煡琛€鑴?鑲濆姛鑳?闃挎墭浼愪粬姹€ 20mg qn	闇€娉ㄦ剰浠栨眬绫昏嵂鐗╃殑鑲濆姛鑳界洃娴嬨€傛偅鑰呴潚闇夌礌杩囨晱锛岄伩鍏嶅惈闈掗湁绱犵被鑽墿銆?2024-06-01 00:00:00	2026-06-18 12:31:21.760181	2026-06-18 12:31:21.760181
1938925a-f2b1-4f24-b03e-dd6d039c4cd2	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	绯栧翱鐥呭璇?鈥?琛€绯栨尝鍔?鍐呭垎娉岀	鏉庣編鐜?杩戜竴鏈堢┖鑵硅绯栧亸楂橈紙7.5-8.5mmol/L锛夛紝椁愬悗2h琛€绯?1-13mmol/L	2鍨嬬硸灏跨梾鐥呭彶8骞达紝鍙ｆ湇浜岀敳鍙岃儘500mg bid+鏍煎垪缇庤劜2mg qd銆傝繎涓€鏈堥ギ椋熸帶鍒舵瑺浣筹紙骞村簳鑱氶澧炲锛夛紝杩愬姩閲忓噺灏戙€傜┖鑵硅绯栧崌鑷?.5-8.5mmol/L锛孒bA1c 7.8%銆備綋閲嶅鍔?kg銆?2鍨嬬硸灏跨梾锛岃绯栨帶鍒朵笉鑹?1. 浜岀敳鍙岃儘璋冩暣涓?000mg bid锛?. 鏍煎垪缇庤劜缁х画2mg qd锛?. 涓ユ牸绯栧翱鐥呴ギ椋燂紝姣忔棩鎬荤儹閲忔帶鍒跺湪1600kcal锛?. 姣忓懆鈮?澶╁揩璧?0鍒嗛挓锛?. 姣忔棩鑷祴绌鸿吂+鐫″墠琛€绯栧苟璁板綍锛?. 杞瘖钀ュ吇绉?浜岀敳鍙岃儘 1000mg bid锛涙牸鍒楃編鑴?2mg qd	鎮ｈ€呭鑽墿璋冩暣瀛樺湪鐒﹁檻锛屽凡璇︾粏瑙ｉ噴璋冩暣鍘熷洜鍜屾敞鎰忎簨椤广€傚缓璁?鍛ㄥ悗澶嶈瘖銆?2025-11-20 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
5b673882-6610-4a1e-b46b-9924e9e414be	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	绯栧翱鐥呭父瑙勫璇?鍐呭垎娉岀	鏉庣編鐜?甯歌鍙栬嵂锛屾棤鐗规畩涓嶉€?琛€绯栨帶鍒跺彲锛岀┖鑵?.0-6.8mmol/L锛岄鍚?h 8-9mmol/L銆傛棤浣庤绯栧彂浣溿€?2鍨嬬硸灏跨梾锛岃嵂鐗╂帶鍒跺彲	缁х画褰撳墠鏂规锛涙瘡涓変釜鏈堝鏌bA1c锛涙瘡骞寸溂搴?瓒抽儴妫€鏌?浜岀敳鍙岃儘 500mg bid锛涙牸鍒楃編鑴?2mg qd	鎮ｈ€呬緷浠庢€уソ銆傛彁閱掓敞鎰忚冻閮ㄦ姢鐞嗐€?2025-06-10 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
eecca68a-5cd8-469b-9026-a43a37467c28	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	report	绯栧翱鐥呭苟鍙戠棁绛涙煡	鍐呭垎娉岀	璧靛崥	骞村害骞跺彂鐥囩瓫鏌?鐪煎簳妫€鏌ワ細杞诲害闈炲娈栨€х硸灏跨梾瑙嗙綉鑶滅梾鍙橈紙鍙岀溂锛夈€傚翱寰噺鐧借泲鐧斤細32mg/g Cr锛堣交搴﹀崌楂橈級銆傜缁忎紶瀵奸€熷害锛氫笅鑲㈣交搴︽劅瑙夌缁忎紶瀵煎噺鎱€?绯栧翱鐥呮棭鏈熷井琛€绠″苟鍙戠棁锛堣缃戣啘鐥呭彉I鏈燂紝鏃╂湡鑲剧梾锛?1. 涓ユ牸鎺у埗琛€绯栵紙绌鸿吂<6.5mmol/L锛岄鍚?h<8mmol/L锛夛紱2. 鍔犵敤鍘勮礉娌欏潶75mg qd淇濇姢鑲惧姛鑳斤紱3. 姣忓崐骞寸溂绉戝鏌ワ紱4. 浣庤泲鐧介ギ椋燂紙姣忔棩0.8g/kg锛?浜岀敳鍙岃儘 500mg bid锛涙牸鍒楃編鑴?2mg qd锛涘巹璐濇矙鍧?75mg qd	鎮ｈ€呭骞跺彂鐥囨劅鍒版媴蹇э紝宸茶缁嗘矡閫氾細鏃╂湡骞查鍙欢缂撹繘灞曘€?2024-03-05 00:00:00	2026-06-18 12:31:21.772269	2026-06-18 12:31:21.772269
64e81b71-9556-4583-841d-334bcb9e2462	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	inpatient	宸﹁啙鍏宠妭缃崲鏈悗浣忛櫌璁板綍	楠ㄧ	寮犲缓鍥?宸﹁啙鍏ㄨ啙鍏宠妭缃崲鏈悗绗?澶?鎮ｈ€呭洜宸﹁啙閲嶅害楠ㄥ叧鑺傜値锛圞ellgren-Lawrence IV绾э級锛屼簬2025-10-04鍦ㄨ叞楹讳笅琛屽乏鑶濆叏鑶濆叧鑺傜疆鎹㈡湳锛圱KA锛夈€傛墜鏈『鍒╋紝鏈腑鍑鸿绾?00ml銆傛湳鍚庡畨杩旂梾鎴裤€?宸﹁啙閲嶅害楠ㄥ叧鑺傜値锛屽叏鑶濆叧鑺傜疆鎹㈡湳鍚?1. 鏈悗24-48h棰勯槻鎬ф姉鐢熺礌锛堝ご瀛㈠憢杈涳紝宸茬‘璁ゆ棤澶村杩囨晱锛夛紱2. 浣庡垎瀛愯倽绱犻闃睤VT锛?. 鏈悗绗?澶╁紑濮婥PM鏈鸿鍔ㄦ椿鍔?韪濇车璁粌锛?. 鏈悗绗?澶╁皾璇曚笅搴婄珯绔嬶紱5. 鐤肩棝绠＄悊锛氬鏉ユ様甯?00mg bid + 鎸夐渶鏇查┈澶?澶村鍛嬭緵 1.5g iv q12h锛堥闃叉劅鏌擄級锛涗綆鍒嗗瓙鑲濈礌 4000IU ih qd锛涘鏉ユ様甯?200mg bid锛涙洸椹 50mg prn	鈿?纾鸿兒绫昏嵂鐗╄繃鏁忥紝閬垮厤浣跨敤纾鸿兒绫诲強鍚：鑳虹粨鏋勮嵂鐗┿€傛湳鍚庡悍澶嶅洟闃熷凡浠嬪叆銆?2025-10-05 00:00:00	2026-06-18 12:31:21.780825	2026-06-18 12:31:21.780825
186ccf35-fb33-44dd-859d-3a7b9d561bff	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	outpatient	鑶濆叧鑺傜疆鎹㈡湳鍚庢媶绾垮鏌?楠ㄧ	寮犲缓鍥?鏈悗涓ゅ懆锛屼激鍙ｆ剤鍚堣壇濂斤紝杞诲害鑲胯儉	鏈悗涓ゅ懆锛屼激鍙ｆ剤鍚堣壇濂斤紝鏃犵孩鑲挎笚娑层€傚乏鑶濆叧鑺傛椿鍔ㄥ害锛氬眻鏇?-85掳锛屼几鐩?掳銆俈AS鐤肩棝璇勫垎2-3鍒嗭紙闈欐伅锛?4-5鍒嗭紙娲诲姩鏃讹級銆傚彲鎷勫弻鎷愯璧般€?宸﹁啙TKA鏈悗鎭㈠鏈燂紙浜屾湡鎰堝悎鑹ソ锛?1. 鎷嗙嚎锛?. 缁х画搴峰璁粌锛岀洰鏍囨湳鍚?鍛ㄥ眻鏇测墺110掳锛?. 閫愭笎鍑忓皯鎷愭潠渚濊禆锛?. 涓€鏈堝悗澶嶈瘖鎷峏鍏夌墖	濉炴潵鏄斿竷 200mg bid prn锛堢柤鐥涙椂鏈嶇敤锛?鎮ｈ€呭悍澶嶉厤鍚堝害杈冩湳鍚庣涓€鍛ㄦ湁鏄庢樉鏀瑰杽銆傞紦鍔辩户缁潥鎸佸悍澶嶈缁冦€?2025-10-18 00:00:00	2026-06-18 12:31:21.780825	2026-06-18 12:31:21.780825
cedc006a-3ad5-4de1-a788-c7db1e43edda	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	emergency	鎬ヨ瘖 鈥?楂樼儹鎯婂帴	鍎跨	鍒樹附鍗?鍙戠儹39.5掳C鎸佺画6灏忔椂锛屼即涓€娆″叏韬娊鎼愮害1鍒嗛挓	鎮ｅ効6宀侊紝杩?澶╂湁杞诲井娴佹稌銆佸挸鍡姐€備粖鏃ユ櫒璧风獊鍙戦珮鐑紝娴嬩綋娓?9.5掳C銆傜害涓婂崍10鏃跺嚭鐜颁竴娆″叏韬娊鎼愶紝鎸佺画绾?鍒嗛挓鍚庤嚜琛岀紦瑙ｏ紝鎰忚瘑鎭㈠銆傛娊鎼愭椂鍙ｅ悙鐧芥搏銆佸弻鐩笂缈汇€傛棦寰€鏃犳儕鍘ュ彶銆?鎬ユ€т笂鍛煎惛閬撴劅鏌擄紱鐑€ф儕鍘ワ紙鍗曠函鍨嬶級锛涢珮鐑?1. 鐗╃悊闄嶆俯+甯冩礇鑺贩鎮恫閫€鐑紙鎸変綋閲嶈绠楋細20mg/kg锛夛紱2. 琛ユ恫锛氬彛鏈嶈ˉ娑茬洂锛?. 瀵嗗垏瑙傚療锛岃嫢鍐嶆鎯婂帴鎴栨寔缁?5鍒嗛挓闇€绱ф€ュ鐞嗭紱4. 鏀跺叆闄㈣瀵?4灏忔椂	甯冩礇鑺贩鎮恫 100mg/5ml锛屾瘡娆?ml prn锛坬6h锛屼綋娓?38.5掳C鏃朵娇鐢級	鈿?澶村绫绘姉鐢熺礌杩囨晱锛岄伩鍏嶄娇鐢ㄣ€傚闀挎瀬搴︾劍铏戯紝宸茶缁嗚В閲婄儹鎬ф儕鍘ラ€氬父棰勫悗鑹ソ銆?2025-12-05 00:00:00	2026-06-18 12:31:21.787797	2026-06-18 12:31:21.787797
612e5742-00e3-47ea-8dbc-53e7385a15e6	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	outpatient	鐑€ф儕鍘ュ悗澶嶈瘖	鍎跨	鍒樹附鍗?浣撴俯宸查檷鑷虫甯革紝浠嶆湁杞诲挸	浣忛櫌瑙傚療3澶╋紝浣撴俯閫愭涓嬮檷鑷虫甯歌寖鍥达紙36.5-37.2掳C锛夛紝鏈啀鍙戠敓鎯婂帴銆備粛鏈夎交搴﹀共鍜筹紝绮剧椋熸鎭㈠銆?涓婂懠鍚搁亾鎰熸煋鎭㈠鏈燂紱鐑€ф儕鍘ワ紙宸茬紦瑙ｏ級	1. 缁х画瑙傚療浣撴俯锛岃嫢鍐嶆鍙戠儹闇€鍙婃椂閫€鐑紱2. 灏忓効姝㈠挸绯栨祮瀵圭棁澶勭悊锛?. 鑻ュ啀娆″彂鐢熸儕鍘ワ紝闇€琛岃剳鐢靛浘妫€鏌ワ紱4. 涓€鍛ㄥ悗澶嶈瘖	灏忓効姝㈠挸绯栨祮 5ml tid锛涘竷娲涜姮澶囩敤锛堜粎鍙戠儹鏃朵娇鐢級	瀹堕暱鎯呯华瓒嬩簬绋冲畾銆傚缓璁涓父澶囬€€鐑嵂鍜屼綋娓╄銆傜儹鎬ф儕鍘ラ€氬父涓鸿壇鎬ц繃绋嬶紝浣嗛渶璀︽儠澶嶅彂銆?2025-12-08 00:00:00	2026-06-18 12:31:21.787797	2026-06-18 12:31:21.787797
d7ba2a96-ca62-453f-8e79-58aea4cfae55	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	蹇冩偢寰呮煡	蹇冨唴绉?鐜嬪織寮?杩戜竴鏈堝弽澶嶅績鎮革紝浼磋兏闂枫€佹皵鐭?鎮ｈ€呰繎涓€鏈堟棤鏄庢樉璇卞洜鍙嶅鍑虹幇蹇冩偢锛屽伓浼磋兏闂枫€佹皵鐭紝姣忔鎸佺画鏁板垎閽熻嚦鍗婂皬鏃朵笉绛夛紝浼戞伅鍚庣紦瑙ｃ€傛棤鑳哥棝銆佹棤鏅曞帴銆傚伐浣滃帇鍔涘ぇ锛屾瘡鏃ュ挅鍟?-3鏉€?蹇冩偢寰呮煡锛氬姛鑳芥€у績寰嬪け甯革紵鐒﹁檻鐘舵€侊紵	1. 24灏忔椂鍔ㄦ€佸績鐢靛浘鐩戞祴锛?. 蹇冭剰褰╄秴锛?. 鐢茬姸鑵哄姛鑳芥鏌ワ紱4. 鍑忓皯鍜栧暋鍥犳憚鍏ワ紱5. 鑻ユ鏌ョ粨鏋滄棤寮傚父锛屽缓璁績鐞嗙鍜ㄨ	鏆傛棤瑙勫緥鐢ㄨ嵂	鈿?闃垮徃鍖规灄杩囨晱锛堣鍙戝摦鍠橈級锛岄伩鍏嶄娇鐢ㄤ换浣曞惈闃垮徃鍖规灄鍙奛SAIDs鑽墿銆傛偅鑰呭伐浣滅箒蹇欙紝寤鸿绾夸笂闂瘖闅忚銆?2025-11-10 00:00:00	2026-06-18 12:31:21.794345	2026-06-18 12:31:21.794345
a8c66372-1343-4a9a-b200-b6a9c9401534	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	涓婅吂鐥涗即鍙嶉吀	娑堝寲鍐呯	鍛ㄦ槑杈?鍙嶅涓婅吂鐥?鏈堬紝椁愬悗鍔犻噸锛屼即鍙嶉吀銆佺儳蹇?鎮ｈ€呰繎2鏈堝弽澶嶄笂鑵归儴闅愮棝锛岄鍚庢槑鏄惧姞閲嶏紝浼村弽閰搞€佽兏楠ㄥ悗鐑х伡鎰熴€傚伓鏈夊闂寸棝銆傝繘椋熻緵杈ｃ€佸挅鍟″悗鍔犻噸銆傝繎涓€鍛ㄧ棁鐘跺姞閲嶏紝鑷鏈嶇敤閾濈⒊閰搁晛鏁堟灉娆犱匠銆?鑳冮绠″弽娴佺梾锛圙ERD锛夛紱鎱㈡€ф祬琛ㄦ€ц儍鐐庯紙寰呰儍闀滅‘璁わ級	1. 濂ョ編鎷夊攽20mg bid椁愬墠锛?. 閾濈⒊閰搁晛鍜€鍤肩墖椁愬悗+鐫″墠prn锛?. 寤鸿琛岃儍闀滄鏌ユ槑纭瘖鏂紱4. 楗璋冩暣锛氬皯椋熷椁愩€侀伩鍏嶅埡婵€鎬ч鐗┿€佺潯鍓?灏忔椂涓嶈繘椋?濂ョ編鎷夊攽 20mg bid锛堥鍓?0min锛夛紱閾濈⒊閰搁晛 1.0g tid prn	鎮ｈ€呭洜宸ヤ綔鍘熷洜鏆傛湭鍋氳儍闀滐紝宸查绾︺€傛敞鎰忎笌蹇冨唴绉戝氨璇婅褰曚氦鍙夊叧鑱斺€斺€旇兏闂蜂篃鍙兘涓嶨ERD鐩稿叧銆?2025-10-20 00:00:00	2026-06-18 12:31:21.794345	2026-06-18 12:31:21.794345
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
57b2cf85-c028-4867-9dff-d908ccb04ca2	9b58578f-8ad3-4a31-8b14-461ef555827f	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	甯垜鏌ヤ竴涓嬫渶杩戠殑鐥呭巻璁板綍	2026-06-18 14:52:01.597112
787e44eb-1c3c-4e44-beb7-c3b2229465ca	9b58578f-8ad3-4a31-8b14-461ef555827f	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	濂界殑锛屽凡涓烘偍鏌ュ埌鏈€杩戠殑涓€鏉＄梾鍘嗚褰曘€俓n灏辫瘖鏃ユ湡锛?025骞?1鏈?0鏃?\n绉戝锛氬績鍐呯锛堜笂娴锋煇闄㈠尯锛?\n鍖荤敓锛氱帇蹇楀己 \n涓昏瘔锛氳繎涓€涓湀鍙嶅蹇冩偢锛屼即鑳搁椃銆佹皵鐭€?\n鐜扮梾鍙诧細鏃犳槑鏄捐鍥犲弽澶嶅嚭鐜板績鎮革紝鍋朵即鑳搁椃銆佹皵鐭紝姣忔鎸佺画鏁板垎閽熻嚦鍗婂皬鏃讹紝浼戞伅鍚庡彲缂撹В銆傛棤鑳哥棝銆佹棤鏅曞帴銆傚伐浣滃帇鍔涘ぇ锛屾瘡澶╁枬鍜栧暋2-3鏉€?\n璇婃柇锛氬績鎮稿緟鏌モ€斺€斿姛鑳芥€у績寰嬪け甯革紵鐒﹁檻鐘舵€侊紵 \n妫€鏌ヤ笌娌荤枟璁″垝锛?\n寤鸿鍋?4灏忔椂鍔ㄦ€佸績鐢靛浘鐩戞祴 \n蹇冭剰褰╄秴 \n鐢茬姸鑵哄姛鑳芥鏌?\n鍑忓皯鍜栧暋鍥犳憚鍏?\n鑻ヤ互涓婃鏌ョ粨鏋滄棤寮傚父锛屽缓璁績鐞嗙鍜ㄨ \n鐢ㄨ嵂鎯呭喌锛氱洰鍓嶆殏鏈寰嬬敤鑽€?\n鐥呭巻鐗瑰埆澶囨敞锛氣殸 鎮ㄥ闃垮徃鍖规灄杩囨晱锛堟浘璇卞彂鍝枠锛夛紝鐥呭巻涓凡鏄庣‘閬垮厤浣跨敤浠讳綍鍚樋鍙稿尮鏋楀強闈炵斁浣撴姉鐐庤嵂锛圢SAIDs锛夌殑鑽墿銆傚氨璇婃椂鍔″繀鎻愰啋鍖荤敓姝よ繃鏁忓彶銆?\n涓汉淇℃伅澶囨敞锛氭偍2025骞存椂宸ヤ綔绻佸繖锛屽亸濂界嚎涓婇棶璇婏紝鑱屼笟涓洪噾铻嶅垎鏋愬笀銆?\n濡傛灉鎮ㄦ兂浜嗚В杩欎唤璁板綍涓殑鍏蜂綋妫€鏌ョ粨鏋滐紙濡傚姩鎬佸績鐢靛浘鎶ュ憡绛夛級锛屾垨闇€瑕佹垜甯偍鏌ユ壘鍏朵粬鏇存棭鐨勭梾鍙诧紝璇峰憡璇夋垜銆備絾璇锋敞鎰忥紝鎴戜笉鑳戒唬鏇垮尰鐢熷仛璇婃柇鎴栧紑鑽紝鎵€鏈夋不鐤楄皟鏁磋涓庢偍鐨勪笓绉戝尰鐢熸矡閫氥€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闃垮徃鍖规灄銆傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-18 14:52:01.617826
27587df9-d947-4b97-826f-44e29afe7e99	ebe35f8c-88df-40a7-9180-b9dbdb4ffa6a	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	甯垜鏌ヤ竴涓嬫渶杩戠殑鐥呭巻璁板綍	2026-06-18 14:57:02.462019
9403bdb2-0c92-43c1-a4cc-fe9d8e5c9409	ebe35f8c-88df-40a7-9180-b9dbdb4ffa6a	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	鏍规嵁鎮ㄦ渶杩戠殑鐥呭巻璁板綍锛?025骞?1鏈?0鏃ワ紝蹇冨唴绉戦棬璇婏級锛屼富瑕佹儏鍐靛涓嬶細\n璇婃柇锛氬績鎮稿緟鏌ワ紝鑰冭檻鍙兘鏄姛鑳芥€у績寰嬪け甯告垨鐒﹁檻鐘舵€併€俓n涓昏鐥囩姸锛氳繎涓€涓湀鏃犳槑鏄捐鍥犲弽澶嶅嚭鐜板績鎮革紝鍋跺皵浼存湁鑳搁椃銆佹皵鐭紝姣忔鎸佺画鍑犲垎閽熷埌鍗婂皬鏃讹紝浼戞伅鍚庤兘缂撹В锛屾病鏈夎兏鐥涙垨鏅曞帴銆傛偍鐩墠宸ヤ綔鍘嬪姏杈冨ぇ锛屾瘡澶╁枬2-3鏉挅鍟°€俓n娌荤枟璁″垝锛歕n 1. 鍋?4灏忔椂鍔ㄦ€佸績鐢靛浘銆俓n 2. 鍋氬績鑴忓僵瓒呫€俓n 3. 妫€鏌ョ敳鐘惰吅鍔熻兘銆俓n 4. 鍑忓皯鍜栧暋鍥犳憚鍏ャ€俓n 5. 濡傛灉妫€鏌ョ粨鏋滄病鏈夊紓甯革紝寤鸿鍘诲績鐞嗙鍜ㄨ銆俓n鐢ㄨ嵂锛氱洰鍓嶆病鏈夎寰嬬敤鑽€俓n閲嶈鎻愰啋锛氭偍鏈夐樋鍙稿尮鏋楄繃鏁忥紙鏇捐鍙戝摦鍠橈級锛岃褰曚腑宸叉槑纭彁閱掗伩鍏嶄娇鐢ㄤ换浣曞惈闃垮徃鍖规灄鎴朜SAIDs锛堥潪鐢句綋鎶楃値鑽級鐨勮嵂鐗┿€俓n濡傛灉鎮ㄩ渶瑕佹洿鏃╃殑璁板綍鎴栨洿璇︾粏鐨勪俊鎭紝鐩墠鏌ヨ鍒扮殑鍙湁杩欎竴鏉★紝鎮ㄥ彲浠ヨ繘涓€姝ヨ鏄庨渶姹傘€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闃垮徃鍖规灄銆傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-18 14:57:02.478586
d19f800f-9c5e-4f28-b662-2d2ff5026e9c	11d41de2-b12a-4288-8c62-cbdd2bec579c	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 02:35:33.894101
02b41378-07e3-4f01-a23e-8ddb7665d066	11d41de2-b12a-4288-8c62-cbdd2bec579c	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忎俊鎭細\n闈掗湁绱犺繃鏁忥細鏇惧嚭鐜扮毊鐤瑰弽搴斻€俓n澶村绫昏嵂鐗╂厧鐢細鍥犳棦寰€鏈夎繃杞诲害鐨柟銆俓n姝ゅ锛屽湪鎮ㄧ殑涓€浠戒綋妫€鎶ュ憡澶勭悊鎰忚涓篃鐗瑰埆澶囨敞浜嗏€滄偅鑰呴潚闇夌礌杩囨晱锛岄伩鍏嶅惈闈掗湁绱犵被鑽墿鈥濄€傝繖浜涗俊鎭潪甯搁噸瑕侊紝鍦ㄦ偍鏈潵灏辫瘖鎴栫敤鑽椂锛屽姟蹇呬富鍔ㄥ憡鐭ュ尰鐢熴€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 02:35:33.924663
0b4d2314-ccd4-4928-ab1f-6a858df1ac18	e74e2a5f-e7d9-4cd4-9dc6-230caa302b38	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	user	鎴戠殑绱ф€ヨ仈绯讳汉鏄皝锛?2026-06-19 02:35:45.380241
12e9af2c-86da-4db5-909c-72faa852d762	e74e2a5f-e7d9-4cd4-9dc6-230caa302b38	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	assistant	鏍规嵁鎮ㄧ殑妗ｆ淇℃伅锛屾偍鐨勭揣鎬ヨ仈绯讳汉鏄細寮犺姵锛堝コ鍎匡級锛岃仈绯荤數璇濓細13700030002銆?2026-06-19 02:35:45.392746
198a5e73-c12d-4de9-8b34-59749b2d0c9e	2f490345-aef7-4044-8f6d-aeba38756c14	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞渶杩戜竴娆＄湅鐥呯殑鍖荤敓鏄皝锛?2026-06-19 02:35:50.708849
9f38bf7a-ee73-4b1b-a9d7-408cff260ee1	2f490345-aef7-4044-8f6d-aeba38756c14	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鎮ㄦ渶杩戜竴娆＄湅鐥呮槸鍦?2025骞?2鏈?鏃ワ紝灏辫瘖绉戝鏄?蹇冨唴绉戯紝鎺ヨ瘖鍖荤敓鏄?鐜嬪織寮?鍖荤敓銆?2026-06-19 02:35:50.716876
45ca9104-478d-43aa-badb-641d751399bd	4c28063b-21b9-4ac8-a24a-ca7cea185db4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 07:15:36.259918
57a1fc76-9307-4e49-9c52-780ce9a380e4	4c28063b-21b9-4ac8-a24a-ca7cea185db4	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忎俊鎭細\n闈掗湁绱犺繃鏁忥細鏇惧嚭鐜拌繃鐨柟銆俓n澶村绫昏嵂鐗╅渶鎱庣敤锛氭棦寰€鏈夎繃杞诲害鐨柟鍙嶅簲銆俓n璇锋敞鎰忥紝鍦ㄤ娇鐢ㄤ换浣曟柊鑽墿鍓嶏紝閮藉簲鍛婄煡鍖荤敓鎮ㄧ殑杩囨晱鍙层€傚鏋滄偍瀵瑰綋鍓嶇殑娌荤枟鏂规鏈夌枒闂紝璇峰挩璇㈡偍鐨勫尰鐢熸垨鑽笀銆俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:15:36.290958
f90dafa5-17a6-489a-a732-27b7edeac170	f1f99f50-81e3-43db-90c0-bfa4033170b1	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 07:16:37.286413
e77cbcf4-4ab9-4350-82fd-b05d6e4a3969	f1f99f50-81e3-43db-90c0-bfa4033170b1	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑妗ｆ璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忎俊鎭細\n闈掗湁绱犵被锛氳繃鏁忥紙鏇惧嚭鐜扮毊鐤癸級銆俓n澶村绫伙細闇€鎱庣敤锛堟偍鏃㈠線鏈夎交搴︾毊鐤瑰彶锛夈€俓n璇锋敞鎰忥紝鍦ㄦ偍涔嬪墠鐨勮鑴傛不鐤楄褰曚腑涔熺壒鍒娉ㄤ簡鈥滄偅鑰呴潚闇夌礌杩囨晱锛岄伩鍏嶅惈闈掗湁绱犵被鑽墿鈥濄€備粖鍚庡氨鍖绘垨鐢ㄨ嵂鏃讹紝璇峰姟蹇呭憡鐭ュ尰鐢熸偍鏈夎繖浜涜繃鏁忓彶銆俓n濡傛灉鎮ㄩ渶瑕佷簡瑙ｆ洿鍏蜂綋鐨勭粏鑺傦紙姣斿杩囨晱褰撴椂鐨勬儏鍐垫垨涓ラ噸绋嬪害锛夛紝鐜版湁璧勬枡涓俊鎭笉澶熷厖鍒嗭紝寤鸿鍜ㄨ鎮ㄧ殑涓绘不鍖荤敓鎴栨煡闃呮洿璇︾粏鐨勮繃鏁忔娴嬫姤鍛娿€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:16:37.303215
5a0397d3-21a6-453a-ad0e-85f53e800d8b	11166174-a144-465b-8769-f85cb18d1147	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 07:17:02.9974
48e0b7a2-4c29-47c1-9079-6e80f7ee9d27	2e6ffee4-25cf-4f5a-9513-db439dbdc845	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	鏍规嵁鎴戠殑鎯呭喌缁欎竴浜涘仴搴峰缓璁?2026-06-19 07:17:59.019421
24badc01-2300-4771-a3fc-b858668ddabd	11166174-a144-465b-8769-f85cb18d1147	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鍖荤枟璁板綍锛屾偍鏈夋槑纭殑鑽墿杩囨晱鍙诧細瀵归潚闇夌礌杩囨晱锛堟浘鍑虹幇杩囩毊鐤癸級銆傚彟澶栵紝澶村绫昏嵂鐗╀篃灞炰簬鎱庣敤鑼冨洿锛堝洜鏃㈠線鏈夎繃杞诲害鐨柟鍙嶅簲锛夈€?\n璇峰姟蹇呯墷璁帮紝鍦ㄥ氨璇婃垨鐢ㄨ嵂鏃朵富鍔ㄥ憡鐭ュ尰鐢熻繖涓€鎯呭喌锛屼互閬垮厤浣跨敤鍚潚闇夌礌鎴栧彲鑳戒氦鍙夎繃鏁忕殑鑽墿銆?\n锛堟敞鎰忥細浠ヤ笂淇℃伅鏉ヨ嚜鎮ㄧ殑鐥呭巻璁板綍锛屽叿浣撶敤鑽柟妗堣浠ュ尰鐢熷綋闈㈣瘎浼颁负鍑嗐€傦級\n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:17:03.008476
641d4630-7906-4cce-8e08-92aaefd13ad5	2e6ffee4-25cf-4f5a-9513-db439dbdc845	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	濂界殑锛屾枃濠凤紝鏍规嵁浣犳渶杩戠殑灏辫瘖璁板綍鍜屾暣浣撴儏鍐碉紝鎴戜负浣犳⒊鐞嗕簡浠ヤ笅鍑犳潯閲嶇偣鍋ュ悍寤鸿銆俓n\n**鏍稿績缁撹锛?* 浣犵洰鍓嶇殑鏍稿績闂鏄?*鑳冮绠″弽娴侊紙GERD锛?* 鍜?*鍘熷洜寰呮煡鐨勫績鎮?*锛屼袱鑰呭彲鑳界浉浜掑奖鍝嶏紝涓斾笌浣犵殑宸ヤ綔鍘嬪姏锛堥噾铻嶅垎鏋愬笀锛夐珮搴︾浉鍏炽€傚缓璁綘浼樺厛鎸夊尰鍢卞畬鎴愭鏌ワ紝鍚屾椂浠?*楗銆佸帇鍔涚鐞嗗拰鐫＄湢**涓変釜缁村害杩涜鐢熸椿璋冩暣銆俓n\n### 1. 鍏充簬娑堝寲绯荤粺锛圙ERD + 鎱㈡€ц儍鐐庯級\n\n- **鐢ㄨ嵂瀹夊叏鎻愰啋锛?* 浣犳鍦ㄦ湇鐢?*濂ョ編鎷夊攽**锛圥PI锛夊拰**閾濈⒊閰搁晛**銆傝鍔″繀鎸夋椂鎸夐噺鏈嶇敤锛岀壒鍒槸濂ョ編鎷夊攽瑕佸湪椁愬墠鏈嶇敤銆備綘鐨勮繃鏁忓彶涓病鏈夋彁鍒拌繖绫昏嵂鐗╋紝鐩墠鏂规鏄畨鍏ㄧ殑銆備絾**璇蜂笉瑕佽嚜琛屽姞鐢ㄤ换浣曟鐥涜嵂鎴栨劅鍐掕嵂**锛屽挨鍏惰璀︽儠鍚湁**甯冩礇鑺€佽悩鏅敓銆佸弻姘姮閰?*绛夐潪鐢句綋鎶楃値鑽紙NSAIDs锛夌殑鑽墿锛屽洜涓哄畠浠拰**闃垮徃鍖规灄**灞炰簬鍚岀被锛屽悓鏍蜂細鍒烘縺鑳冮粡鑶滐紝鍔犻噸浣犵殑鑳冪梾銆俓n- **楗璋冩暣锛堟牳蹇冿級锛?*\n    - **灏戦澶氶**锛氬皢涓夐鍒嗘垚浜斿埌鍏皬椁愶紝閬垮厤杩囬ケ銆俓n    - **缁濆閬垮厤**锛氬挅鍟°€佹祿鑼躲€佸阀鍏嬪姏銆佺⒊閰搁ギ鏂欍€佽緵杈ｆ补鐐搁鐗┿€佽繃鐢滅殑椋熺墿锛堝铔嬬硶銆佸ザ鑼讹級銆傝繖浜涢兘浼氱洿鎺ヨ鍙戝弽娴佸拰蹇冩偢銆俓n    - **鐫″墠涔犳儻**锛氱潯鍓?灏忔椂鍐?*缁濆涓嶈杩涢**锛屽寘鎷枬姘淬€傜潯瑙夋椂鍙互绋嶅井鍨珮搴婂ご銆俓n- **鑳冮暅妫€鏌ュ缓璁細** 浣犲凡缁忛绾︿簡鑳冮暅锛岃鍔″繀瀹屾垚銆傝繖鏄槑纭瘖鏂參鎬ц儍鐐庡拰鎺掗櫎鍏朵粬闂鐨勯噾鏍囧噯锛屼笉瑕佸洜涓哄伐浣滃繖鑰屾帹杩熴€俓n\n### 2. 鍏充簬蹇冭剰闂锛堝績鎮稿緟鏌ワ級\n\n- **绉瀬閰嶅悎妫€鏌ワ細** 浣犳鍦ㄥ仛**24灏忔椂鍔ㄦ€佸績鐢靛浘**鍜?*蹇冭剰褰╄秴**锛岃繖鏄帓鏌ュ績寰嬪け甯稿拰蹇冭剰缁撴瀯闂鐨勫叧閿€傚彟澶栵紝鍖荤敓杩樺缓璁簡**鐢茬姸鑵哄姛鑳芥鏌?*锛岃鍔″繀鍔犱笂銆傚洜涓虹敳鐘惰吅鍔熻兘寮傚父锛堢敳浜€佺敳鍑忥級閮戒細寮曡捣蹇冩偢锛岃€屼綘姣嶄翰鏈夌敳鍑忕梾鍙诧紝杩欎竴鐐瑰浣犲緢閲嶈銆俓n- **鍜栧暋鍥犵鐞嗭細** 鍖荤敓鏄庣‘寤鸿鍑忓皯鍜栧暋鍥犳憚鍏ャ€備綔涓洪噾铻嶅垎鏋愬笀锛屽挅鍟″彲鑳芥槸浣犵殑鏃ュ父浼翠荆锛屼絾瀹冩槸蹇冩偢鍜屽弽娴佺殑鍏卞悓璇卞洜銆?*璇峰皾璇曠敤浣庡洜鍜栧暋鎴栬崏鏈尪锛堝娲嬬敇鑿婅尪锛夋浛浠?*锛屽苟璁板綍涓ゅ懆鍐呯殑蹇冩偢鍙戜綔棰戠巼鏈夋棤鏀瑰杽銆俓n- **鍘嬪姏涓庢儏缁細** 鍔熻兘鎬у績寰嬪け甯稿拰鐒﹁檻鐘舵€侀珮搴︾浉鍏炽€備綘鐨勫伐浣滆妭濂忓揩銆佸帇鍔涘ぇ锛岃繖鏄噸瑕佺殑璇卞彂鍥犵礌銆傚缓璁細\n    - **姝ｅ康鍛煎惛缁冧範**锛氭瘡澶╄姳5-10鍒嗛挓锛屼笓娉ㄥ懠鍚革紝鑳藉揩閫熻皟鑺傚績鐜囥€俓n    - **瀹氭椂璧风珛娲诲姩**锛氭瘡宸ヤ綔45鍒嗛挓锛岀珯璧锋潵璧板姩2鍒嗛挓锛屽仛鍑犱釜娣卞懠鍚革紝鑳芥湁鏁堢紦瑙ｇ揣寮犮€俓n\n### 3. 缁煎悎鐢熸椿鏂瑰紡寤鸿\n\n- **杩愬姩锛?* 閬垮厤鍓х儓杩愬姩锛堝楂樺己搴﹂棿姝囪缁冿級锛屼互鍏嶈鍙戝績鎮搞€傛帹鑽?*鏁ｆ銆佺憸浼姐€佹父娉?*绛夎垝缂撹繍鍔ㄣ€傛瘡娆?0鍒嗛挓锛屾瘡鍛ㄨ嚦灏?娆°€傝繍鍔ㄥ悗娉ㄦ剰琛ュ厖姘村垎銆俓n- **鐫＄湢锛?* 灏介噺淇濊瘉姣忔櫄7-8灏忔椂鐫＄湢銆傚鏋滃洜鍘嬪姏澶辩湢锛岀潯鍓?灏忔椂杩滅鎵嬫満鍜岀數鑴戯紝鍙互灏濊瘯鍚櫧鍣煶鎴栧仛鎷変几銆俓n- **澶嶈瘖璺熻釜锛?* 浣犱笅鍛ㄩ渶瑕佸甫缁撴灉鍘?*蹇冨唴绉戝璇婏紙鐜嬪尰鐢燂級**锛屼袱鍛ㄥ悗涔熻鍘?*娑堝寲鍐呯澶嶈瘖锛堝懆鍖荤敓锛屽甫鑳冮暅缁撴灉锛?*銆傝鍔″繀鎸夋椂鍘汇€傚鏋滃績鎮稿姞閲嶏紝浼撮殢鑳哥棝銆佸ご鏅曟垨鐪煎墠鍙戦粦锛岃绔嬪嵆鍘绘€ヨ瘖銆俓n\n### 鐗瑰埆鎻愰啋锛堣繃鏁忓彶鐩稿叧锛塡n\n浣犲凡鐭ュ**闃垮徃鍖规灄**锛堣鍙戝摦鍠橈級鍜?*鑺辩矇**杩囨晱銆傛湭鏉ュ鏋滈渶瑕佷换浣曟不鐤楋紙濡傚叧鑺傜値銆佹劅鍐掑彂鐑с€佺柤鐥涚瓑锛夛紝**蹇呴』鏄庣‘鍛婄煡鍖荤敓浣犵殑闃垮徃鍖规灄杩囨晱鍙插拰鍝枠鐥呭彶**銆傚尰鐢熶細涓轰綘閫夋嫨瀹夊叏鐨勬浛浠ｈ嵂鐗╋紙濡傚涔欓叞姘ㄥ熀閰氱瓑锛夈€俓n\n鎬荤粨锛氫綘鐩墠鐨勫仴搴烽棶棰樺睘浜庡吀鍨嬬殑鈥滆韩蹇冪柧鐥呪€濓紝娑堝寲鍜屽績鑴忕殑鐥囩姸閮戒笌涓灑绁炵粡绯荤粺锛堝帇鍔涖€佺劍铏戯級瀵嗗垏鐩稿叧銆?*鍏堜緷璧栨鏌ユ帓闄ゅ櫒璐ㄦ€х梾鍙橈紝鍐嶉€氳繃鐢熸椿鏂瑰紡骞查瑙ｅ喅鍔熻兘鎬ч棶棰?*锛岃繖鏄渶閫傚悎浣犵殑璺緞銆傜浣犳棭鏃ュ悍澶嶏紒\n\n---\n鈿狅笍 **瀹夊叏鎻愰啋**锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 **闃垮徃鍖规灄銆佽姳绮?*銆傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗?*宸茬煡杩囨晱**銆傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:17:59.029469
15ea8efb-212e-4894-a5f7-5c63afa52bc9	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	涓婃灏辫瘖鐨勮瘖鏂粨鏋?2026-06-19 07:26:30.344938
9636fa13-2e8a-4655-8e14-f3d6798d8619	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	user	浣犳槸璋佸憿锛?2026-06-19 07:37:03.447362
b50eb8e5-3aae-4578-b0f7-7eb2c41969fd	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	鏍规嵁鎮ㄦ渶杩戠殑鍖荤枟璁板綍锛屾偍鏈€杩戜竴娆″氨璇婏紙2025骞?1鏈?0鏃ワ紝蹇冨唴绉戯級鐨勮瘖鏂粨鏋滄槸锛氬績鎮稿緟鏌ワ紝鍖荤敓鍒濇鑰冭檻鍙兘涓?鍔熻兘鎬у績寰嬪け甯?鎴?鐒﹁檻鐘舵€?鏈夊叧銆俓n鐩墠璇婃柇杩樻湭瀹屽叏鏄庣‘锛屽洜涓哄尰鐢熷綋鏃朵负鎮ㄥ紑鍏蜂簡 24灏忔椂鍔ㄦ€佸績鐢靛浘 鍜?蹇冭剰褰╄秴 妫€鏌ワ紝杩欎簺妫€鏌ョ粨鏋滄槸鍚﹀凡缁忓洖鎶ャ€佺粨鏋滃浣曪紝鐜版湁淇℃伅涓苟鏈褰曘€傚洜姝わ紝灏氫笉娓呮鏈€缁堢殑鏄庣‘璇婃柇鏄粈涔堛€俓n鍙﹀锛岄渶瑕佹彁閱掓偍娉ㄦ剰鍑犵偣锛歕n妫€鏌ョ粨鏋滐細鎮ㄤ笂娆″氨璇婂悗鏄惁宸插畬鎴愬姩鎬佸績鐢靛浘鍜屽績鑴忓僵瓒咃紵濡傛灉宸插畬鎴愶紝寤鸿甯︾潃缁撴灉灏藉揩澶嶈瘖锛堝師璁″垝鏄竴鍛ㄥ悗鎼哄甫缁撴灉澶嶈瘖锛夈€俓n鐥囩姸鐩戞祴锛氬鏋滃績鎮搞€佽兏闂风棁鐘跺姞閲嶏紝鎴栧嚭鐜拌兏鐥涖€佹檿鍘ョ瓑鏂版儏鍐碉紝璇峰強鏃跺幓鎬ヨ瘖銆俓n楗涓庝綔鎭細鍖荤敓寤鸿鍑忓皯鍜栧暋鍥犳憚鍏ワ紙鎮ㄥ綋鏃舵瘡澶╁枬2-3鏉挅鍟★級锛屽悓鏃舵偍鍥犲伐浣滃帇鍔涘ぇ锛屽缓璁€傚綋璋冩暣浣滄伅銆佺鐞嗘儏缁€俓n杩囨晱鎻愰啋锛氭偍瀵归樋鍙稿尮鏋楄繃鏁忥紙浼氳鍙戝摦鍠橈級锛屾墍鏈夊惈闃垮徃鍖规灄鎴栧悓绫昏嵂鐗╋紙濡傚竷娲涜姮绛夐潪鐢句綋鎶楃値鑽級閮藉簲涓ユ牸閬垮厤銆俓n姝ゅ锛屾偍鍦?025骞?0鏈?0鏃ユ秷鍖栧唴绉戠殑灏辫瘖璇婃柇鏄細鑳冮绠″弽娴佺梾锛圙ERD锛?鍜屽彲鑳界殑 鎱㈡€ф祬琛ㄦ€ц儍鐐庯紙寰呰儍闀滅‘璁わ級锛屽綋鏃跺凡寮€濮嬫湇鐢ㄥゥ缇庢媺鍞戞不鐤楋紝骞朵笖棰勭害浜嗚儍闀溿€傝繖閮ㄥ垎鎯呭喌涔熻缁х画鎸夋秷鍖栫鍖荤敓鐨勬柟妗堥殢璁裤€俓n濡傛灉鎮ㄦ槸闇€瑕佹垜鍥為【鏇存棭涔嬪墠锛堟瘮濡傞娆℃秷鍖栧唴绉戝氨璇婏級鐨勮瘖鏂鎯咃紝璇峰憡璇夋垜锛屾垜鍙互缁х画涓烘偍鎻愪緵銆俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闃垮徃鍖规灄銆傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:26:30.350378
a372b889-6a03-4422-b5d8-1a21dd39df29	9984be28-353e-4562-b830-bae32d3c876a	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 07:27:18.815743
68ee17b2-12ee-483c-99ac-c9ce2dff9808	9984be28-353e-4562-b830-bae32d3c876a	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍瀵归潚闇夌礌杩囨晱锛堟浘鏈夌毊鐤瑰弽搴旓級銆傛澶栵紝鐥呭巻涓繕鎻愮ず澶村绫昏嵂鐗╅渶鎱庣敤锛屽洜涓烘偍鏃㈠線鏈夎交搴︾毊鐤瑰彶銆?\n涓庡尰鐢熸矡閫氭垨寮€鑽椂锛岃鍔″繀涓诲姩鍛婄煡涓婅堪杩囨晱鎯呭喌銆俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 07:27:18.823955
fcbb4467-b60e-4e45-bc4e-daf4c962bea1	f96b1a3f-f421-4ecc-92ba-867dd776e701	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	assistant	鎴戞槸鎮ㄧ殑涓浗鍖荤枟鍔╂墜锛屽彲浠ヨ浣忔偍涔嬪墠鐨勫璇濆拰鍋ュ悍淇℃伅銆傛垜灏嗗敖鍔涗负鎮ㄦ彁渚涗笓涓氥€佸畨鍏ㄧ殑鍖荤枟鐩稿叧寤鸿锛屼絾璇锋敞鎰忔垜涓嶈兘浠ｆ浛鍖荤敓鍋氭渶缁堣瘖鏂垨寮€鑽€傛湁浠€涔堝仴搴锋柟闈㈢殑闂锛岄殢鏃跺彲浠ラ棶鎴戙€?2026-06-19 07:37:03.458198
089103e4-93d4-4e59-b3db-4af64bb9faeb	3ae9c7ad-0e65-4ebd-b778-c64eb570d2dd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 13:47:46.965206
ed499a85-cc72-4b6a-8127-f519cd312009	3ae9c7ad-0e65-4ebd-b778-c64eb570d2dd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈夋槑纭殑鑽墿杩囨晱鍙诧細瀵归潚闇夌礌杩囨晱锛堟浘鍑虹幇鐨柟锛夛紝骞朵笖澶村绫昏嵂鐗╅渶瑕佹厧鐢紙鏃㈠線鏈夎交搴︾毊鐤硅褰曪級銆傚叾浠栬嵂鐗╃洰鍓嶆湭瑙佽繃鏁忚褰曘€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 13:47:46.98315
50ab4e70-9a76-4dd5-8ee6-fe86f1c7da10	1ac4c2df-4a85-4cc1-a63f-ecb3059ea4fb	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 13:51:28.332936
75cf3919-6f0a-4bf5-a0cd-f08615336e63	1ac4c2df-4a85-4cc1-a63f-ecb3059ea4fb	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忓彶锛歕n闈掗湁绱犵被锛氭偍瀵归潚闇夌礌杩囨晱锛屾浘鍑虹幇杩囩毊鐤广€俓n澶村鑿岀礌绫伙細鍖荤敓娉ㄦ槑闇€鎱庣敤锛屽洜涓烘棦寰€鏈夎繃杞诲害鐨柟銆俓n璇锋偍鍔″繀鍦ㄥ氨璇婂拰鐢ㄨ嵂鏃讹紝涓诲姩鍛婄煡鍖荤敓鍜岃嵂甯堜互涓婅繃鏁忎俊鎭€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 13:51:28.345327
8e42af6f-02ce-4421-a809-c788fd2ce07a	3cb6d386-c40a-402e-bb72-ffb999556a05	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 13:52:22.534465
3b64f2dd-c29b-4978-9295-2b2f277fcf85	3cb6d386-c40a-402e-bb72-ffb999556a05	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忎俊鎭細\n闈掗湁绱犺繃鏁忥細鏇惧嚭鐜拌繃鐨柟銆俓n澶村绫绘姉鐢熺礌闇€鎱庣敤锛氭棦寰€鏈夎繃杞诲害鐨柟銆俓n鍥犳锛屾偍鍦ㄥ氨璇婃椂鍔″繀涓诲姩鍛婄煡鍖荤敓杩欎簺杩囨晱鎯呭喌锛岀壒鍒槸褰撳尰鐢熻€冭檻浣跨敤鎶楃敓绱犳椂銆俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 13:52:22.544044
1c038b02-0db5-41e9-bb34-4288fed54c86	0b9534c6-d9d0-487e-85c3-f69e1aa0afba	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 13:57:03.748923
759fbb83-bb87-49c0-93eb-a1c08481305f	0b9534c6-d9d0-487e-85c3-f69e1aa0afba	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鍋ュ悍妗ｆ璁板綍锛屾偍瀵归潚闇夌礌杩囨晱锛堟浘鏈夌毊鐤瑰弽搴旓級锛屽悓鏃跺ご瀛㈢被鑽墿涔熼渶瑕佹厧閲嶄娇鐢紙鏃㈠線鏈夎繃杞诲害鐨柟锛夈€傜敤鑽椂璇锋敞鎰忓憡鐭ュ尰鐢熻繖浜涙儏鍐碉紝鍏蜂綋鍝簺鑽笉鑳界敤銆佽兘鍚︽崲鐢ㄥ叾浠栬嵂锛岄渶瑕佺敱鍖荤敓缁撳悎鎮ㄧ殑瀹為檯鐥呮儏鏉ュ垽鏂€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 13:57:03.761169
dccca7b5-7ece-4329-b23d-cc282c6bb921	e17177ad-9a98-4677-a720-fa9dc232d6fd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	user	鎴戞湁浠€涔堣嵂鐗╄繃鏁忓悧锛?2026-06-19 14:19:53.892611
7f545765-cedc-41c8-b092-2961dd80ab48	e17177ad-9a98-4677-a720-fa9dc232d6fd	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	assistant	鏍规嵁鎮ㄧ殑鐥呭巻璁板綍锛屾偍鏈変互涓嬭嵂鐗╄繃鏁忎俊鎭細瀵归潚闇夌礌杩囨晱锛堟浘鍑虹幇鐨柟锛夛紝鍙﹀澶村绫绘姉鐢熺礌闇€瑕佹厧鐢紙鏃㈠線鏈夎交搴︾毊鐤瑰彶锛夈€傝鎮ㄥ湪灏卞尰鎴栫敤鑽椂鍔″繀鍛婄煡鍖荤敓杩欎簺鎯呭喌锛岄伩鍏嶄娇鐢ㄧ浉鍏宠嵂鐗┿€俓n---\n鈿狅笍 瀹夊叏鎻愰啋锛氱郴缁熸娴嬪埌鍥炵瓟涓彁鍒颁簡 闈掗湁绱犮€傛牴鎹偅鑰呮。妗堬紝鎮ｈ€呭璇ヨ嵂鐗╁凡鐭ヨ繃鏁忋€傝鍦ㄧ敤鑽墠鍔″繀纭鎮ｈ€呯殑杩囨晱鍙诧紝閬垮厤浣跨敤杩囨晱鑽墿銆?2026-06-19 14:19:53.913351
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
0824dacc-c921-4305-bb05-3215f5d9698c	b544a617-8863-4f92-85b7-c4b4de121321	\N	user	浣犲ソ	2026-06-18 07:07:12.109156
5776fb17-18f4-455a-a4d3-7aa0e5885dcc	b544a617-8863-4f92-85b7-c4b4de121321	\N	assistant	浣犲ソ锛佹垜鏄綘鐨勫仴搴峰姪鐞嗭紝鏈変粈涔堝彲浠ュ府浣犵殑鍚楋紵濡傛灉鏈変换浣曡韩浣撲笉閫傛垨鍋ュ悍鏂归潰鐨勭枒闂紝閮藉彲浠ュ憡璇夋垜銆傛垜浼氬敖鍔涗负浣犳彁渚涗笓涓氱殑鍒嗘瀽鍜屽缓璁€?2026-06-18 07:07:12.151313
ec349ec9-9538-4f5e-a3ec-1cffbcc0feaa	aee61297-af16-4156-8a72-454ab1fd4c1e	\N	user	浣犲ソ鍛€浣犳槸璋?2026-06-18 11:26:50.490683
ad88e091-b941-47c0-9d2e-f0b57448db90	aee61297-af16-4156-8a72-454ab1fd4c1e	\N	assistant	浣犲ソ鍛€锛佹垜鏄皬鍠勶紝浣犵殑涓枃鍖荤枟鍔╂墜锛屼笓闂ㄥ府浣犺В绛斿仴搴风浉鍏崇殑鐤戦棶銆佹彁渚涘尰瀛︾煡璇嗗拰鏃ュ父淇濆仴寤鸿鐨勩€傛垜涓嶆槸鐪熸鐨勫尰鐢燂紝涓嶈兘鍋氳瘖鏂垨寮€鑽紝浣嗘垜浼氬敖鏈€澶у姫鍔涚粰浣犳彁渚涢潬璋便€佸畨鍏ㄧ殑淇℃伅銆傛湁浠€涔堥棶棰樺敖绠￠棶鎴戝惂锛屽挶浠參鎱㈣亰锝?2026-06-18 11:26:50.540787
9d1211d6-afb8-45de-a00d-eeffde1fab4c	56fa4f24-39a8-4635-9b02-87dbbefbc5c1	\N	user	浣犲ソ	2026-06-18 13:28:16.228095
440f42b3-91bb-417c-9bef-be7fa7875c4f	56fa4f24-39a8-4635-9b02-87dbbefbc5c1	\N	assistant	浣犲ソ锛佹垜鏄綘鐨勬櫤鑳藉仴搴峰姪鎵嬶紝鏈変粈涔堣韩浣撲笉閫傛垨鍋ュ悍鏂归潰鐨勯棶棰樺彲浠ラ殢鏃跺憡璇夋垜銆備负浜嗚兘鏇村噯纭湴甯綘鍒嗘瀽锛屽彲浠ュ厛鍛婅瘔鎴戜綘鐨勫勾榫勩€佹€у埆锛屼互鍙婃湁娌℃湁鑽墿杩囨晱鍙插悧锛熻繖鏍锋垜浼氭洿璋ㄦ厧鍦扮粰鍑哄缓璁€?2026-06-18 13:28:16.274082
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
3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	P0002	鏋楃編濞?female	1975-08-22	13900020001	\N	\N	涓婃捣甯傚緪姹囧尯婕曟渤娉惧紑鍙戝尯鐢版灄璺?00鍙?02瀹?鏋楀織寮猴紙鍎垮瓙锛?13900020002	O	鏃犲凡鐭ヨ嵂鐗╄繃鏁?姣嶄翰锛?鍨嬬硸灏跨梾銆侀珮琛€鍘嬶紱鐖朵翰锛氫綋鍋ワ紱鏈夌硸灏跨梾瀹舵棌鑱氶泦鍊惧悜	瀵圭敤鑽皟鏁磋緝鐒﹁檻锛岄渶瑕佽€愬績瑙ｉ噴锛涜亴涓氾細鍏徃璐㈠姟	t	2026-06-18 12:31:21.75667	2026-06-18 12:31:21.75667
8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	P0003	寮犲浗鏍?male	1955-03-15	13700030001	\N	\N	鍖椾含甯傛湞闃冲尯鏈涗含琛楅亾鑺卞鍦板寳閲?鍙锋ゼ3鍗曞厓102	寮犺姵锛堝コ鍎匡級	13700030002	B	纾鸿兒绫昏嵂鐗╄繃鏁忥紙鍏ㄨ韩鐨柟+鍙戠儹锛夛紱閰掔簿杩囨晱锛堥潰閮ㄦ疆绾級	鐖朵翰锛氶鍏宠妭鐐庛€侀珮琛€鍘嬶紱姣嶄翰锛氫綋鍋?闇€瑕佽疆妞呰緟鍔╋紱鏈悗搴峰璁粌閰嶅悎搴︿竴鑸紝闇€瑕佸榧撳姳锛涜亴涓氾細閫€浼戝伐浜?t	2026-06-18 12:31:21.770251	2026-06-18 12:31:21.770251
3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	P0004	鍚村皬闆?female	2019-11-28	13600040001	\N	\N	涓婃捣甯傞椀琛屽尯鑾樺簞闀囪帢寤鸿矾100鍙?01瀹?鍚村缓鍥斤紙鐖朵翰锛?13600040002	AB	澶村绫绘姉鐢熺礌杩囨晱锛堟棦寰€娉ㄥ皠澶村鏇叉澗鍚庡嚭鐜拌崹楹荤柟锛?鐖朵翰锛氳繃鏁忔€ч蓟鐐庯紱姣嶄翰锛氫綋鍋ワ紱鏃犳槑纭仐浼犵梾鍙?瀹堕暱鐒﹁檻绋嬪害杈冮珮锛屽氨璇婃椂闇€棰濆瀹夋姎锛涢渶娉ㄦ剰鐢ㄨ嵂鍓傞噺鎸変綋閲嶈绠?t	2026-06-18 12:31:21.778836	2026-06-18 12:31:21.778836
fea79596-6296-4112-9b79-547826c93ebd	hospital-b	P1001	閮戞枃濠?female	1982-07-03	13500050001	\N	\N	涓婃捣甯傞潤瀹夊尯鍗椾含瑗胯矾1266鍙锋亽闅嗗箍鍦洪檮杩?閮戠锛堝摜鍝ワ級	13500050002	A	闃垮徃鍖规灄杩囨晱锛堣鍙戝摦鍠橈級锛涜姳绮夎繃鏁忥紙瀛ｈ妭鎬э級	鐖朵翰锛氶珮琛€鍘嬨€佽儍婧冪枴锛涙瘝浜诧細鐢茬姸鑵哄姛鑳藉噺閫€	宸ヤ綔绻佸繖锛屽亸濂界嚎涓婇棶璇婏紱璺ㄩ櫌鍖哄氨璇婏紙hospital-a蹇冨唴绉戯紝hospital-b娑堝寲绉戯級锛涜亴涓氾細閲戣瀺鍒嗘瀽甯?t	2026-06-18 12:31:21.785564	2026-06-18 12:31:21.785564
e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	P0001	闄堝缓鍥?male	1968-05-10	13800010001	\N	\N	涓婃捣甯傛郸涓滄柊鍖哄紶姹熼晣纰ф尝璺?88寮?2鍙?01瀹?闄堟锛堥厤鍋讹級	13800010002	A	闈掗湁绱犺繃鏁忥紙鐨柟锛夛紱澶村绫绘厧鐢紙鏃㈠線杞诲害鐨柟锛?鐖朵翰锛氶珮琛€鍘嬨€佸啝蹇冪梾锛?8宀佸績姊楀幓涓栵紱姣嶄翰锛氶珮琛€鍘嬶紝鍋ュ湪	test update OK	t	2026-06-18 12:31:21.752354	2026-06-18 15:18:27.668473
\.


--
-- Data for Name: visit_records; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.visit_records (id, patient_id, hospital_id, visit_type, department, doctor_name, campus, chief_complaint, visit_status, visit_summary, follow_up_plan, visit_date, created_at, updated_at) FROM stdin;
33938f3f-5336-4c73-95ec-cd1497c6971b	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	蹇冨唴绉?鐜嬪織寮?鏈儴闄㈠尯	鏅ㄨ捣澶存檿涓ゅ懆锛屼即杞诲井蹇冩偢	completed	琛€鍘嬫帶鍒舵瑺浣筹紝璋冩暣闄嶅帇鏂规锛氱棘娌欏潶鍔犻噺+鍔犵敤姘ㄦ隘鍦板钩銆傚槺浣庣洂楗銆佸搴鍘嬬洃娴嬨€備袱鍛ㄥ悗澶嶈瘖銆?涓ゅ懆鍚庡璇婂績鍐呯锛屽鏌ヨ鍘?蹇冪數鍥俱€傚悓姝ュ鏌ヨ鑴傦紙涓婃浣撴琛€鑴傚亸楂橈級銆?2025-12-01 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
339612e0-c551-40ce-b944-ad7ce258d8ea	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	蹇冨唴绉?鐜嬪織寮?鏈儴闄㈠尯	甯歌鍙栬嵂澶嶆煡	completed	琛€鍘嬫帶鍒惰壇濂斤紝缁х画褰撳墠鏂规銆傚父瑙勫彇鑽棘娌欏潶3涓湀鐢ㄩ噺銆?涓変釜鏈堝悗澶嶈瘖鍙栬嵂銆?2025-09-15 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
c129ba4b-824c-425f-b841-d7ad5662ace3	e6164450-3f38-4d09-9230-d98ec2899237	hospital-a	outpatient	浣撴涓績	闄堝缓鍗?鏈儴闄㈠尯	骞村害浣撴鎶ュ憡瑙ｈ	completed	浣撴绀洪珮鑴傝鐥囷紝缁欎簣闃挎墭浼愪粬姹€娌荤枟銆傚缓璁敓娲绘柟寮忓共棰勩€?6鍛ㄥ悗澶嶆煡琛€鑴?鑲濆姛鑳姐€?2024-06-01 00:00:00	2026-06-18 12:31:21.764181	2026-06-18 12:31:21.764181
b681a4a2-4890-461a-b5a3-f2c974429d15	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	outpatient	鍐呭垎娉岀	鏉庣編鐜?鏈儴闄㈠尯	琛€绯栨尝鍔紝椁愬悗鍋忛珮	completed	琛€绯栨帶鍒朵笉鑹紝璋冩暣浜岀敳鍙岃儘鍓傞噺銆傝浆璇婅惀鍏荤杩涜楗鎸囧銆傛偅鑰呭鑽墿璋冩暣瀛樺湪鐒﹁檻锛屽凡璇︾粏瑙ｉ噴銆?涓夊懆鍚庡璇婂唴鍒嗘硨绉戯紝绌鸿吂+椁愬悗2h琛€绯?HbA1c銆傚悓姝ヨ惀鍏荤闂ㄨ瘖銆?2025-11-20 00:00:00	2026-06-18 12:31:21.776276	2026-06-18 12:31:21.776276
dbcf202b-ebe4-462e-8a36-2e15a269bc43	3cc3cc4b-1640-4323-9356-2e75e1b40d28	hospital-a	follow_up	鍐呭垎娉岀	鏉庣編鐜?鏈儴闄㈠尯	甯歌鍙栬嵂锛屾棤鐗规畩涓嶉€?completed	琛€绯栨帶鍒跺彲锛屽父瑙勫彇鑽€傛彁閱掕冻閮ㄦ姢鐞嗗拰骞村害鐪煎簳妫€鏌ャ€?姣忎笁涓湀澶嶈瘖鍙栬嵂銆備粖骞村唴瀹屾垚鐪煎簳妫€鏌ャ€?2025-06-10 00:00:00	2026-06-18 12:31:21.776276	2026-06-18 12:31:21.776276
a84fb6b2-7653-48ff-9c72-82b6c1c7f6cf	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	inpatient	楠ㄧ	寮犲缓鍥?鏈儴闄㈠尯	宸﹁啙閲嶅害楠ㄥ叧鑺傜値锛屽叆闄㈣鍏宠妭缃崲鏈?admitted	鍏ラ櫌琛屽乏鑶濆叏鑶濆叧鑺傜疆鎹㈡湳銆傛湳鍓嶈瘎浼帮細蹇冭偤鍔熻兘鍙紝鎵嬫湳椋庨櫓鍙帶銆傛敞鎰忕：鑳鸿繃鏁忓彶銆?鏈悗2鍛ㄦ媶绾垮鏌ワ紱鏈悗6鍛╔鍏夌墖+鍔熻兘璇勪及锛涙湳鍚?/6/12鏈堝畾鏈熷鏌ャ€?2025-10-04 00:00:00	2026-06-18 12:31:21.782539	2026-06-18 12:31:21.782539
4e8e6820-2437-48cd-8606-c588ae32fdfe	8be5c5da-b39f-4ec4-a930-e8197055bcaa	hospital-a	follow_up	楠ㄧ	寮犲缓鍥?鏈儴闄㈠尯	鍏宠妭缃崲鏈悗2鍛ㄦ媶绾?澶嶆煡	completed	浼ゅ彛鎰堝悎鑹ソ锛屾媶绾裤€傚叧鑺傛椿鍔ㄥ害鍙紙灞堟洸0-85掳锛夈€傜户缁悍澶嶈缁冿紝榧撳姳澧炲姞娲诲姩閲忋€?涓€鏈堝悗鎷峏鍏夌墖澶嶆煡銆傚悍澶嶇缁х画闅忚銆?2025-10-18 00:00:00	2026-06-18 12:31:21.782539	2026-06-18 12:31:21.782539
e3ad33ec-be5f-470c-b0d3-e5f45936febb	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	emergency	鍎跨	鍒樹附鍗?鏈儴闄㈠尯	楂樼儹39.5掳C锛屾娊鎼愪竴娆?admitted	鎬ユ€т笂鍛煎惛閬撴劅鏌撳悎骞剁儹鎬ф儕鍘ャ€傜粰浜堥€€鐑€佽ˉ娑插鐞嗭紝鏀跺叆闄㈣瀵熴€傚闀跨劍铏戯紝宸插畨鎶氬苟璇︾粏瑙ｉ噴鐥呮儏銆?浣忛櫌瑙傚療3澶╋紝绋冲畾鍚庡嚭闄€傚嚭闄?澶╁悗澶嶈瘖銆傝嫢鍐嶆鎯婂帴闇€琛岃剳鐢靛浘銆?2025-12-05 00:00:00	2026-06-18 12:31:21.790809	2026-06-18 12:31:21.790809
4f82b3f7-a8cc-4aec-826e-a85ed0558413	3620e203-31b8-4303-941e-5e1e3022aafe	hospital-a	follow_up	鍎跨	鍒樹附鍗?鏈儴闄㈠尯	鐑€€锛岃交鍜筹紝澶嶈瘖璇勪及	completed	浣撴俯姝ｅ父锛屾湭鍐嶆儕鍘ャ€傜簿绁為娆叉仮澶嶏紝杞诲挸瀵圭棁澶勭悊銆傚闀挎儏缁ǔ瀹氥€?涓€鍛ㄥ悗澶嶈瘖銆傚涓父澶囬€€鐑嵂銆傝嫢鍙戠儹闇€鍙婃椂閫€鐑鐞嗭紝璀︽儠鎯婂帴澶嶅彂銆?2025-12-08 00:00:00	2026-06-18 12:31:21.790809	2026-06-18 12:31:21.790809
f9cffd3b-2697-4776-9728-7724e324e386	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	蹇冨唴绉?鐜嬪織寮?鏈儴闄㈠尯	鍙嶅蹇冩偢銆佽兏闂?completed	蹇冩偢寰呮煡锛屽凡寮€鍏峰姩鎬佸績鐢靛浘鍜屽績鑴忓僵瓒咃紝寰呯粨鏋滃洖鎶ャ€傚缓璁噺灏戝挅鍟″洜鎽勫叆銆?涓€鍛ㄥ悗鎼哄甫妫€鏌ョ粨鏋滃璇婂績鍐呯銆傝嫢蹇冩偢鍔犻噸闅忔椂鎬ヨ瘖銆?2025-11-10 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
7c0d09d2-f23c-427b-bb1f-eac670c5529d	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	娑堝寲鍐呯	鍛ㄦ槑杈?涓滈櫌鍖?涓婅吂鐥涖€佸弽閰搞€佺儳蹇?completed	璇婃柇GERD+鎱㈡€ц儍鐐庡彲鑳斤紝鍚姩PPI娌荤枟銆傝儍闀滃凡棰勭害锛屽緟妫€鏌ユ槑纭瘖鏂€?涓ゅ懆鍚庢秷鍖栧唴绉戝璇婏紙鎼哄甫鑳冮暅缁撴灉锛夈€傝嵂鏁堣瘎浼板悗鍐冲畾鏄惁璋冩暣鏂规銆?2025-10-20 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
1428212a-83af-495f-9c35-ef9f19777041	fea79596-6296-4112-9b79-547826c93ebd	hospital-b	outpatient	娑堝寲鍐呯	鍛ㄦ槑杈?涓滈櫌鍖?鍋跺皵鍙嶉吀锛岄娆″氨璇?completed	鐥囩姸杈冭交锛屽缓璁敓娲绘柟寮忚皟鏁达細灏戦澶氶銆侀伩鍏嶅埡婵€鎬ч鐗┿€傛殏涓嶇敤鑽瀵熴€?鑻ョ棁鐘舵寔缁垨鍔犻噸鍒欏璇娿€?2025-09-01 00:00:00	2026-06-18 12:31:21.796852	2026-06-18 12:31:21.796852
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


