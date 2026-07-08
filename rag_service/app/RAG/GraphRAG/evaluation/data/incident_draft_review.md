# Incident Draft Review Sheet

ตรวจแต่ละข้อ: (1) สำนวนเหมือนสำนวนคดีจริงไหม (2) cue ตรงกับ technique จริงไหม
(3) step แบบ described ไม่เผลอบอกชื่อเทคนิค — แก้ไขในไฟล์ incident_draft.json
แล้วลบข้อที่ใช้ไม่ได้ทิ้ง

## inc_auto_001  (source group: FIN7 G0046)

**AUTO-FLAGS: step 4: cue not found verbatim in narrative**

> ผู้เสียหายรายงานว่าระบบเครือข่ายของสำนักงานราชการแห่งหนึ่งถูกเข้าถึงโดยไม่ได้รับอนุญาตในวันที่ 15 พฤศจิกายน เมื่อผู้โจมตีใช้ Valid Accounts ของพนักงานที่ลาออกแล้วเพื่อเข้าสู่ระบบ VPN จากนั้นผู้โจมตีได้ดำเนินการสคริปต์อัตโนมัติ (PowerShell script) บนเครื่องสถานีงานเพื่อสร้างบัญชีผู้ใช้ที่ซ่อนอยู่และรวบรวมข้อมูลประจำตัว ต่อมาจากการตรวจสอบพบว่ามีการคัดลอกไฟล์ลับไปยัง USB drive ที่เชื่อมต่อกับระบบ และไฟล์เหล่านั้นถูกแพร่กระจายไปยังเครื่องอื่นๆ ผ่าน shared folders จากนั้นผู้โจมตีได้ใช้ Exploitation of Remote Services เพื่อเข้าถึงเซิร์ฟเวอร์ฐานข้อมูลหลัก (database server) โดยผ่านช่องโหว่ใน RDP protocol สุดท้ายผู้โจมตีได้ทำการ Ingress Tool Transfer โดยดาวน์โหลดเครื่องมือ reconnaissance และ persistence tools จากเซิร์ฟเวอร์ภายนอกมายังระบบภายใน

*EN:* The victim organization, a government office, reported that their network system was accessed without authorization on November 15. The attacker used Valid Accounts belonging to a former employee to gain access to the VPN. Subsequently, the attacker executed an automated PowerShell script on workstations to create hidden user accounts and harvest credentials. Investigation revealed that confidential files were copied to a USB drive connected to the system, and those files were propagated to other machines via shared folders. The attacker then used Exploitation of Remote Services to compromise the primary database server by leveraging a vulnerability in the RDP protocol. Finally, the attacker performed Ingress Tool Transfer by downloading reconnaissance and persistence tools from external servers into the internal network.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 Valid Accounts | ผู้โจมตีใช้ Valid Accounts ของพนักงานที่ลาออกแล้วเพื่อเข้าสู่ระบบ VPN |
| 2 | described | T1064 Scripting | ผู้โจมตีได้ดำเนินการสคริปต์อัตโนมัติ (PowerShell script) บนเครื่องสถานีงานเพื่อสร้างบัญชีผู้ใช้ที่ซ่อนอยู่และรวบรวมข้อมูลประจำตัว |
| 3 | described | T1091 Replication Through Removable Media | มีการคัดลอกไฟล์ลับไปยัง USB drive ที่เชื่อมต่อกับระบบ และไฟล์เหล่านั้นถูกแพร่กระจายไปยังเครื่องอื่นๆ ผ่าน shared folders |
| 4 | named | T1210 Exploitation of Remote Services | ผู้โจมตีได้ใช้ Exploitation of Remote Services เพื่อเข้าถึงเซิร์ฟเวอร์ฐานข้อมูลหลัก โดยผ่านช่องโหว่ใน RDP protocol |
| 5 | named | T1105 Ingress Tool Transfer | ผู้โจมตีได้ทำการ Ingress Tool Transfer โดยดาวน์โหลดเครื่องมือ reconnaissance และ persistence tools จากเซิร์ฟเวอร์ภายนอก |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_002  (source group: APT29 G0016)

**AUTO-FLAGS: step 2: described cue names the technique (Windows Management Instrumentation)**

> ผู้เสียหายรายงานว่าระบบ Windows Server ของหน่วยงานบริหารสินทรัพย์ได้รับการบุกรุกในวันที่ 15 มีนาคม 2567 โดยเริ่มจากการติดต่อทางอีเมลที่ปลอมแปลงจากเจ้าหน้าที่ IT ของบริษัทจัดหาบริการ cloud ที่มีความสัมพันธ์ในการทำงานกับหน่วยงานมาเป็นเวลานาน ซึ่งเป็น Trusted Relationship ที่ผู้โจมตีนำมาใช้เพื่อเข้าถึงระบบ จากการตรวจสอบ Event Log พบว่ามีกระบวนการ wmic.exe ถูกเรียกใช้ด้วยพารามิเตอร์ที่ผิดปกติเพื่อทำการ Windows Management Instrumentation ในการรันสคริปต์ VBScript ที่ซ่อนอยู่ในระบบไฟล์ชั่วคราว ต่อมาผู้โจมตีได้ใช้บัญชีผู้ใช้งานที่ถูกต้องตามชื่อ svc-backup ซึ่งเป็นบัญชีบริการที่มีสิทธิ์เข้าถึงข้อมูลสำคัญ และกิจกรรมการเข้าถึงดังกล่าวไม่ได้ทำให้เกิดการแจ้งเตือนความผิดปกติในระบบตรวจสอบ จากนั้นผู้โจมตีได้ทำการ Exploitation for Privilege Escalation ผ่านช่องโหว่ CVE-2021-1732 ในไดรเวอร์ Win32k เพื่อยกระดับสิทธิ์จาก user ไปเป็น system จากนั้นทำการ Data from Local System โดยการคัดลอกไฟล์ฐานข้อมูล SQL Server ที่มีข้อมูลบัญชีเงินฝากของลูกค้ามากกว่า 50,000 รายไปยังไดเรกทอรี่ที่ซ่อนอยู่บนเซิร์ฟเวอร์ภายในเครือข่าย

*EN:* The victim reported that a Windows Server system of an asset management agency was breached on 15 March 2567, beginning with a spoofed email from an IT officer of a cloud service provider that had an established working relationship with the agency, which was a Trusted Relationship exploited by the attacker to gain initial system access. Upon investigation of Event Logs, abnormal wmic.exe processes were discovered being invoked with unusual parameters to perform Windows Management Instrumentation by executing a VBScript hidden in the system temporary directory. Subsequently, the attacker utilized a valid account named svc-backup, which is a service account with privileged access to sensitive data, and the access activity did not trigger anomaly alerts in the monitoring system. The attacker then performed Exploitation for Privilege Escalation via CVE-2021-1732 vulnerability in the Win32k driver to elevate privileges from user to system level. Finally, Data from Local System was extracted by copying SQL Server database files containing customer deposit account information for more than 50,000 customers to a hidden directory on an internal network server.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1199 Trusted Relationship | Trusted Relationship ที่ผู้โจมตีนำมาใช้เพื่อเข้าถึงระบบ |
| 2 | described | T1047 Windows Management Instrumentation | มีกระบวนการ wmic.exe ถูกเรียกใช้ด้วยพารามิเตอร์ที่ผิดปกติเพื่อทำการ Windows Management Instrumentation ในการรันสคริปต์ VBScript |
| 3 | described | T1078 Valid Accounts | ผู้โจมตีได้ใช้บัญชีผู้ใช้งานที่ถูกต้องตามชื่อ svc-backup ซึ่งเป็นบัญชีบริการที่มีสิทธิ์เข้าถึงข้อมูลสำคัญ และกิจกรรมการเข้าถึงดังกล่าวไม่ได้ทำให้เกิดการแจ้งเตือนความผิดปกติ |
| 4 | named | T1068 Exploitation for Privilege Escalation | ผู้โจมตีได้ทำการ Exploitation for Privilege Escalation ผ่านช่องโหว่ CVE-2021-1732 ในไดรเวอร์ Win32k เพื่อยกระดับสิทธิ์จาก user ไปเป็น system |
| 5 | named | T1005 Data from Local System | ทำการ Data from Local System โดยการคัดลอกไฟล์ฐานข้อมูล SQL Server ที่มีข้อมูลบัญชีเงินฝากของลูกค้า |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_003  (source group: Earth Lusca G1006)

> ผู้เสียหายรายงานว่าระบบเซิร์ฟเวอร์ Windows ของส่วนราชการแห่งหนึ่งถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ Event Viewer และไฟล์ Task Scheduler พบว่ามีการสร้างงานประจำที่ (scheduled task) ชื่อ "SystemUpdate" ที่ตั้งเวลาให้ทำงานทุกชั่วโมง โดยเรียกไฟล์ executable ที่ซ่อนอยู่ในโฟลเดอร์ System32 ต่อมาจากการตรวจสอบ log ของ netstat และ DNS query history พบหลักฐานว่าเครื่องดำเนินการสอบถามการกำหนดค่าเครือข่าย (ipconfig, route print, arp -a) และเก็บรวบรวมข้อมูลเกี่ยวกับโทโพโลยีเครือข่ายภายในส่วนราชการ จากนั้นจากการวิเคราะห์ proxy logs และ firewall rules พบว่าการสื่อสารแบบ proxy ถูกใช้เพื่อเชื่อมต่อไปยังเซิร์ฟเวอร์ภายนอก ผ่านพอร์ต 8080 และ 3128 ซึ่งบ่งชี้ว่ามีการใช้ proxy เป็นชองทางสำหรับการควบคุมและสั่งการระยะไกล

*EN:* The victim organization, a government agency, reported unauthorized access to its Windows server infrastructure. Upon investigation of Event Viewer and Task Scheduler files, a scheduled task named "SystemUpdate" was discovered, configured to execute hourly and invoke a hidden executable in the System32 folder. Subsequent analysis of netstat logs and DNS query history revealed evidence of network configuration discovery activities (ipconfig, route print, arp -a commands) and collection of internal network topology data. Further examination of proxy logs and firewall rules identified proxy-based communication channels used to establish command-and-control connections to external servers via ports 8080 and 3128, indicating the use of proxy infrastructure for remote command and control.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1053 Scheduled Task/Job | มีการสร้างงานประจำที่ (scheduled task) ชื่อ "SystemUpdate" ที่ตั้งเวลาให้ทำงานทุกชั่วโมง โดยเรียกไฟล์ executable ที่ซ่อนอยู่ในโฟลเดอร์ System32 |
| 2 | described | T1016 System Network Configuration Discovery | เครื่องดำเนินการสอบถามการกำหนดค่าเครือข่าย (ipconfig, route print, arp -a) และเก็บรวบรวมข้อมูลเกี่ยวกับโทโพโลยีเครือข่ายภายในส่วนราชการ |
| 3 | named | T1090 Proxy | มีการใช้ proxy เป็นชองทางสำหรับการควบคุมและสั่งการระยะไกล |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_004  (source group: Dragonfly G0035)

> ผู้เสียหายรายงานว่า ระบบ Active Directory ของบริษัทได้รับการเข้าถึงโดยใช้ Valid Accounts ของพนักงานแผนกไอทีที่ลาออกไปแล้ว ต่อมาจากการตรวจสอบ Windows Event Log พบว่ามีการสร้างและรันงาน Scheduled Task ที่ทำให้เกิดการเรียกใช้งาน PowerShell script ทุกชั่วโมง จากนั้นผู้สอบสวนตรวจพบการแก้ไข Registry ในส่วน HKLM\Software\Microsoft\Windows\CurrentVersion\Run เพื่อให้มัลแวร์โหลดตัวเองขึ้นมาทุกครั้งที่ระบบเปิด ภายหลังพบว่าผู้โจมตีได้ใช้ประโยชน์จากช่องโหว่ใน RDP service ของเซิร์ฟเวอร์อีกเครื่องหนึ่งในเครือข่าย เพื่อขยายการเข้าถึง สุดท้ายจากการสอบสวน Disk forensics พบไฟล์ที่ถูกบีบอัดด้วย Archive Collected Data ที่มีขนาด 2.3 GB ซึ่งเก็บรวบรวมเอกสารสำคัญและฐานข้อมูลลูกค้า

*EN:* The victim reported that the company's Active Directory system was accessed using Valid Accounts belonging to a former IT department employee. Upon examination of Windows Event Logs, investigators found the creation and execution of a Scheduled Task that invoked PowerShell scripts hourly. Subsequently, examiners discovered modifications to the Registry in HKLM\Software\Microsoft\Windows\CurrentVersion\Run to load malware at every system startup. Later, it was determined that the attacker exploited a vulnerability in the RDP service of another server within the network to expand access. Finally, disk forensics revealed compressed archive files containing 2.3 GB of collected corporate documents and customer database records.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 Valid Accounts | ใช้ Valid Accounts ของพนักงานแผนกไอทีที่ลาออกไปแล้ว |
| 2 | described | T1053 Scheduled Task/Job | มีการสร้างและรันงาน Scheduled Task ที่ทำให้เกิดการเรียกใช้งาน PowerShell script ทุกชั่วโมง |
| 3 | named | T1112 Modify Registry | การแก้ไข Registry ในส่วน HKLM\Software\Microsoft\Windows\CurrentVersion\Run |
| 4 | described | T1210 Exploitation of Remote Services | ผู้โจมตีได้ใช้ประโยชน์จากช่องโหว่ใน RDP service ของเซิร์ฟเวอร์อีกเครื่องหนึ่งในเครือข่าย |
| 5 | named | T1560 Archive Collected Data | ไฟล์ที่ถูกบีบอัดด้วย Archive Collected Data ที่มีขนาด 2.3 GB ซึ่งเก็บรวบรวมเอกสารสำคัญและฐานข้อมูลลูกค้า |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_005  (source group: Silence G0091)

> ผู้เสียหายรายงานว่าระบบ Active Directory ของบริษัทประกันภัยแห่งหนึ่งถูกเข้าถึงโดยใช้บัญชีพนักงานที่ถูกต้องตามปกติในวันที่ 15 มีนาคม เวลา 02:47 น. จากการตรวจสอบ event log พบว่าผู้โจมตีใช้ Microsoft SCCM (Systems Center Configuration Manager) ซึ่งเป็นเครื่องมือ deployment ที่ติดตั้งอยู่แล้ว เพื่อดำเนินการ script execution บนเครื่องคอมพิวเตอร์จำนวน 47 เครื่องในเครือข่าย ต่อมาผู้โจมตีทำการ Ingress tool transfer โดยโหลด Mimikatz และเครื่องมือ reconnaissance อื่นๆ จากเซิร์ฟเวอร์ภายนอกมายังเครื่องที่ติดตั้ง SCCM agent จากนั้นใช้เครื่องมือดังกล่าวเพื่อทำ Screen capture ของหน้าจอ 23 เครื่องที่มีสิทธิ์สูง เก็บรูปภาพไว้ที่โฟลเดอร์ temp ในหน่วยความจำ สุดท้ายจากการวิเคราะห์ network traffic พบว่าข้อมูลที่ถูกเก็บรวบรวมถูกส่งออกไปยังเซิร์ฟเวอร์ C2 ผ่าน Non-standard port 8843 ในช่วงเวลา 03:15 น. ถึง 04:22 น.

*EN:* The victim, an insurance company, reported that their Active Directory system was accessed using valid employee credentials on 15 March at 02:47. Log analysis revealed that the attacker used Microsoft SCCM (Systems Center Configuration Manager), an already-installed deployment tool, to execute scripts on 47 computers across the network. Subsequently, the attacker performed Ingress tool transfer by loading Mimikatz and other reconnaissance tools from an external server onto the SCCM agent machine. The tools were then used to perform Screen capture of 23 high-privilege workstations, with images stored in temporary memory folders. Finally, network traffic analysis showed that collected data was exfiltrated to a C2 server via Non-standard port 8843 between 03:15 and 04:22.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 Valid Accounts | ระบบ Active Directory ของบริษัทประกันภัยแห่งหนึ่งถูกเข้าถึงโดยใช้บัญชีพนักงานที่ถูกต้องตามปกติ |
| 2 | described | T1072 Software Deployment Tools | ผู้โจมตีใช้ Microsoft SCCM (Systems Center Configuration Manager) ซึ่งเป็นเครื่องมือ deployment ที่ติดตั้งอยู่แล้ว เพื่อดำเนินการ script execution |
| 3 | named | T1105 Ingress Tool Transfer | ผู้โจมตีทำการ Ingress tool transfer โดยโหลด Mimikatz และเครื่องมือ reconnaissance อื่นๆ จากเซิร์ฟเวอร์ภายนอก |
| 4 | named | T1113 Screen Capture | ใช้เครื่องมือดังกล่าวเพื่อทำ Screen capture ของหน้าจอ 23 เครื่องที่มีสิทธิ์สูง |
| 5 | named | T1571 Non-Standard Port | ข้อมูลที่ถูกเก็บรวบรวมถูกส่งออกไปยังเซิร์ฟเวอร์ C2 ผ่าน Non-standard port 8843 |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_006  (source group: Turla G0010)

> ผู้เสียหายรายงานว่าระบบ Windows Server ของหน่วยงานราชการแห่งหนึ่งถูกจ้างหนุน โดยผู้โจมตีได้เรียกใช้ Windows API โดยตรงเพื่อเรียกใช้ payload ที่ซ่อนอยู่ในหน่วยความจำ จากนั้นผู้โจมตีได้ทำการแก้ไขค่า registry หลายรายการเพื่อให้โปรแกรมที่ติดตั้งนั้นทำงานอัตโนมัติทุกครั้งที่ระบบเริ่มต้น ต่อมาจากการตรวจสอบไฟล์ log พบว่าผู้โจมตีได้ทำการ deobfuscate/decode files ที่เก็บไว้ในโฟลเดอร์ temp เพื่อเข้าถึงคำสั่งที่ซ่อนอยู่ จากนั้นผู้โจมตีได้ทำการค้นหาเวลาระบบปัจจุบันโดยการเรียกใช้ API เพื่อตรวจสอบว่าระบบได้ถูกกำหนดเวลาไว้อย่างไร ต่อมาผู้โจมตีได้ทำการโอนย้ายเครื่องมือ exploitation ไปยังเครื่องคอมพิวเตอร์อื่นในเครือข่ายภายในผ่านการแชร์ไฟล์เครือข่าย สุดท้ายผู้โจมตีได้ทำการเก็บรวบรวมข้อมูลจำเพาะจากระบบท้องถิ่น เช่น ไฟล์ config ฐานข้อมูล และข้อมูลประจำตัวผู้ใช้ที่เก็บไว้ในเครื่องเซิร์ฟเวอร์ต้นทาง

*EN:* The victim reported that a Windows Server system at a government agency was compromised when the attacker invoked Windows API directly to execute a payload residing in memory. The attacker then modified multiple registry values to ensure the installed program ran automatically on every system startup. Upon log file examination, it was discovered that the attacker had deobfuscated/decoded files stored in the temp folder to access hidden commands. Subsequently, the attacker queried system time by invoking API calls to determine how the system clock was configured. The attacker then transferred exploitation tools to other computers on the internal network via network file sharing. Finally, the attacker collected specific data from the local system, including configuration files, databases, and user credentials stored on the source server.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1106 Native API | ผู้โจมตีได้เรียกใช้ Windows API โดยตรงเพื่อเรียกใช้ payload ที่ซ่อนอยู่ในหน่วยความจำ |
| 2 | described | T1112 Modify Registry | ผู้โจมตีได้ทำการแก้ไขค่า registry หลายรายการเพื่อให้โปรแกรมที่ติดตั้งนั้นทำงานอัตโนมัติทุกครั้งที่ระบบเริ่มต้น |
| 3 | named | T1140 Deobfuscate/Decode Files or Information | ผู้โจมตีได้ทำการ deobfuscate/decode files ที่เก็บไว้ในโฟลเดอร์ temp เพื่อเข้าถึงคำสั่งที่ซ่อนอยู่ |
| 4 | described | T1124 System Time Discovery | ผู้โจมตีได้ทำการค้นหาเวลาระบบปัจจุบันโดยการเรียกใช้ API เพื่อตรวจสอบว่าระบบได้ถูกกำหนดเวลาไว้อย่างไร |
| 5 | described | T1570 Lateral Tool Transfer | ผู้โจมตีได้ทำการโอนย้ายเครื่องมือ exploitation ไปยังเครื่องคอมพิวเตอร์อื่นในเครือข่ายภายในผ่านการแชร์ไฟล์เครือข่าย |
| 6 | described | T1005 Data from Local System | ผู้โจมตีได้ทำการเก็บรวบรวมข้อมูลจำเพาะจากระบบท้องถิ่น เช่น ไฟล์ config ฐานข้อมูล และข้อมูลประจำตัวผู้ใช้ที่เก็บไว้ในเครื่องเซิร์ฟเวอร์ต้นทาง |

- [ ] ผ่าน / แก้แล้ว
