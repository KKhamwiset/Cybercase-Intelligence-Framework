# Incident Draft Review Sheet

ตรวจแต่ละข้อ: (1) สำนวนเหมือนสำนวนคดีจริงไหม (2) cue ตรงกับ technique จริงไหม
(3) step แบบ described ไม่เผลอบอกชื่อเทคนิค — แก้ไขในไฟล์ incident_draft.json
แล้วลบข้อที่ใช้ไม่ได้ทิ้ง

## inc_auto_001  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนแห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบคอมพิวเตอร์เซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบพยานหลักฐานดิจิทัล พบว่าผู้โจมตีได้ใช้ Modify Registry เพื่อปิดใช้งานซอฟต์แวร์ป้องกันระบบและซ่อนการทำงานของมัลแวร์ ต่อมา ผู้โจมตีได้สำเร็จในการแพร่กระจายตัวอ่อนของมัลแวร์ไปยังอุปกรณ์ USB และหน่วยเก็บข้อมูลเคลื่อนที่อื่นๆ เพื่อสามารถแพร่ไปยังเครื่องอื่นในเครือข่ายได้ จากนั้น ผู้โจมตีได้ดำเนินการเรียกดูและสกัดข้อมูลไฟล์ที่สำคัญจากเซิร์ฟเวอร์ เช่น ฐานข้อมูลลูกค้า เอกสารทางการเงิน และแผนการธุรกิจ ผ่านการเชื่อมต่อ reverse shell ที่ติดตั้งไว้ สุดท้าย ผู้โจมตีได้ถ่ายโอนข้อมูลที่เก็บรวบรวมได้ออกจากระบบไปยังเซิร์ฟเวอร์ควบคุมระยะไกลผ่านช่องทางการสื่อสารที่ถูกสร้างขึ้นเพื่อวัตถุประสงค์นี้

*EN:* On 22 February 2569, a private company in Samut Prakan Province reported unauthorized access to its primary server system. Digital forensic examination revealed that the attacker used Modify Registry to disable security software and conceal malware activity. Subsequently, the attacker successfully propagated malware variants to USB devices and removable storage media to spread across networked machines. The attacker then extracted critical data files from the server, including customer databases, financial documents, and business plans via an installed reverse shell connection. Finally, the attacker transferred the collected data out of the system to a remote control server through an established communication channel.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1112 modify registry | ผู้โจมตีได้ใช้ Modify Registry เพื่อปิดใช้งานซอฟต์แวร์ป้องกันระบบและซ่อนการทำงานของมัลแวร์ |
| 2 | named | T1091 ? | ผู้โจมตีได้สำเร็จในการแพร่กระจายตัวอ่อนของมัลแวร์ไปยังอุปกรณ์ USB และหน่วยเก็บข้อมูลเคลื่อนที่อื่นๆ เพื่อสามารถแพร่ไปยังเครื่องอื่นในเครือข่ายได้ |
| 3 | described | T1005 ? | ผู้โจมตีได้ดำเนินการเรียกดูและสกัดข้อมูลไฟล์ที่สำคัญจากเซิร์ฟเวอร์ เช่น ฐานข้อมูลลูกค้า เอกสารทางการเงิน และแผนการธุรกิจ ผ่านการเชื่อมต่อ reverse shell ที่ติดตั้งไว้ |
| 4 | described | T1105 ? | ผ่านการเชื่อมต่อ reverse shell ที่ติดตั้งไว้ |
| 5 | described | T1041 ? | ผู้โจมตีได้ถ่ายโอนข้อมูลที่เก็บรวบรวมได้ออกจากระบบไปยังเซิร์ฟเวอร์ควบคุมระยะไกลผ่านช่องทางการสื่อสารที่ถูกสร้างขึ้นเพื่อวัตถุประสงค์นี้ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_002  (source group: (previous run) )

> เมื่อวันที่ 8 กุมภาพันธ์ 2569 บริษัทเอกชนด้านเทคโนโลยีแห่งหนึ่งในจังหวัดนนทบุรีแจ้งความว่าระบบเซิร์ฟเวอร์ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Valid Accounts ของพนักงานอดีตที่ยังไม่ถูกปิดการใช้งาน เพื่อเข้าสู่ระบบ RDP ในเวลา 02:47 น. ต่อมาจากการตรวจสอบ Registry บน Windows Server พบว่ามีการแก้ไขค่า HKLM\System\CurrentControlSet\Services ซึ่งเห็นได้ว่าผู้โจมตีได้ปรับเปลี่ยนการตั้งค่าเกี่ยวกับบริการระบบไฟล์ และการบันทึกข้อมูล จากนั้นผู้โจมตีได้ทำการ File and Directory Discovery โดยค้นหาไฟล์ประเภท .bak, .sql, และ .xlsx ในโฟลเดอร์ C:\Users และ D:\Database โดยใช้คำสั่ง dir และ findstr สุดท้ายพบว่าผู้โจมตีได้ทำการ Inhibit System Recovery โดยลบไฟล์ Volume Shadow Copy และปิดการใช้งาน Windows Backup Service ทำให้ผู้ดูแลระบบไม่สามารถกู้คืนข้อมูลได้

*EN:* On 8 February 2569, a private technology company in Nonthaburi Province reported unauthorized access to its server system. Log analysis revealed that the attacker used Valid Accounts of a former employee whose credentials had not been disabled to access the RDP system at 02:47. Subsequent examination of the Windows Server Registry showed modifications to HKLM\System\CurrentControlSet\Services, indicating the attacker had altered settings related to file system services and logging mechanisms. The attacker then performed File and Directory Discovery, searching for .bak, .sql, and .xlsx files in C:\Users and D:\Database directories using dir and findstr commands. Finally, the attacker executed Inhibit System Recovery by deleting Volume Shadow Copy files and disabling the Windows Backup Service, preventing system administrators from restoring data.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 valid accounts | ผู้โจมตีได้ใช้ Valid Accounts ของพนักงานอดีตที่ยังไม่ถูกปิดการใช้งาน เพื่อเข้าสู่ระบบ RDP |
| 2 | described | T1112 modify registry | มีการแก้ไขค่า HKLM\System\CurrentControlSet\Services ซึ่งเห็นได้ว่าผู้โจมตีได้ปรับเปลี่ยนการตั้งค่าเกี่ยวกับบริการระบบไฟล์ และการบันทึกข้อมูล |
| 3 | named | T1083 ? | ผู้โจมตีได้ทำการ File and Directory Discovery โดยค้นหาไฟล์ประเภท .bak, .sql, และ .xlsx ในโฟลเดอร์ C:\Users และ D:\Database |
| 4 | named | T1490 inhibit system recovery | ผู้โจมตีได้ทำการ Inhibit System Recovery โดยลบไฟล์ Volume Shadow Copy และปิดการใช้งาน Windows Backup Service |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_003  (source group: (previous run) )

**AUTO-FLAGS: step 3: described cue names the technique (os credential dumping)**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานคร แจ้งความว่าระบบเซิร์ฟเวอร์สำนักงานใหญ่ถูกเข้าถึงข้อมูลโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ระบบพบว่าผู้โจมตีได้ใช้ Valid Accounts ของพนักงานที่ออกจากงานแล้วเพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่อง ต่อมาจากการวิเคราะห์ไฟล์ system registry พบหลักฐานว่าผู้โจมตีได้ดำเนินการแก้ไขค่า configuration ของ Windows Defender และปิดการใช้งาน antivirus software โดยการปรับเปลี่ยนค่าในส่วน Group Policy เพื่อหลีกเลี่ยงการตรวจจับ จากนั้นผู้โจมตีได้ทำการ OS Credential Dumping ด้วยการรัน tool ที่ใช้เข้าถึง LSASS process เพื่อสกัดรหัสผ่านและ hash จากหน่วยความจำของระบบ สุดท้าย พบหลักฐานว่าผู้โจมตีได้ทำการ Archive Collected Data โดยการบีบอัดไฟล์ข้อมูลสำคัญเป็นไฟล์ RAR และเก็บไว้ในโฟลเดอร์ temp ก่อนทำการส่งออกจากระบบ

*EN:* On 22 February 2569, a private financial company in Bangkok reported unauthorized access to its headquarters server system. Investigation of system logs revealed that the attacker used Valid Accounts belonging to a former employee to maintain persistent access to the system. Subsequent analysis of system registry files showed evidence that the attacker had modified Windows Defender configuration values and disabled antivirus software by adjusting Group Policy settings to evade detection. The attacker then performed OS Credential Dumping by running a tool to access the LSASS process to extract passwords and hashes from system memory. Finally, evidence was found that the attacker performed Archive Collected Data by compressing sensitive data files into a RAR archive and storing it in a temp folder before exfiltration.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 valid accounts | ผู้โจมตีได้ใช้ Valid Accounts ของพนักงานที่ออกจากงานแล้ว |
| 2 | described | T1553 ? | ผู้โจมตีได้ดำเนินการแก้ไขค่า configuration ของ Windows Defender และปิดการใช้งาน antivirus software โดยการปรับเปลี่ยนค่าในส่วน Group Policy |
| 3 | described | T1003 os credential dumping | ผู้โจมตีได้ทำการ OS Credential Dumping ด้วยการรัน tool ที่ใช้เข้าถึง LSASS process เพื่อสกัดรหัสผ่านและ hash จากหน่วยความจำของระบบ |
| 4 | named | T1560 archive collected data | ผู้โจมตีได้ทำการ Archive Collected Data โดยการบีบอัดไฟล์ข้อมูลสำคัญเป็นไฟล์ RAR |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_004  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้รับแจ้งเบาะแสจากผู้ดูแลระบบว่าพบกิจกรรมที่น่าสงสัยบนเซิร์ฟเวอร์ Windows Server จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ System Binary Proxy Execution ผ่านเครื่องมือ certutil.exe เพื่อดาวน์โหลดไฟล์ payload ไปยังเครื่องจักรเป้าหมาย ต่อมาจากการวิเคราะห์การเชื่อมต่อเครือข่าย พบว่ามีการสร้างช่องทางการติดต่อกลับผ่านบริการ RDP ที่ยังเปิดใช้งานอยู่บนพอร์ตที่ไม่ใช่มาตรฐาน ซึ่งใช้เป็นจุดทำให้มีการเข้าถึงระบบอย่างต่อเนื่อง จากนั้นผู้โจมตีได้ใช้บัญชีผู้ใช้ที่มีอยู่แล้วในระบบซึ่งดูเหมือนว่าเป็นบัญชีพนักงานที่ยังคงใช้งานอยู่ เพื่อเพิ่มสิทธิการเข้าถึงไปยังเครื่องจักรอื่นในเครือข่าย สุดท้ายพบว่าผู้โจมตีได้ทำการ Credentials from Password Stores โดยใช้เครื่องมือประเภท credential dumping เพื่อดึงข้อมูลรหัสผ่านจากที่เก็บข้อมูลในระบบปฏิบัติการ นอกจากนี้ยังพบการเรียกใช้คำสั่ง System Time Discovery เพื่อตรวจสอบเวลาระบบ และการถ่ายโอนเครื่องมือไซเบอร์ต่างๆ เข้ามาในระบบเพื่อใช้ในการโจมตีต่อเนื่อง

*EN:* On 22 February 2569, an information technology services company in Bangkok received notification from a system administrator regarding suspicious activity on a Windows Server. Log analysis revealed that the attacker used System Binary Proxy Execution via certutil.exe to download payload files to the target machine. Subsequently, network connection analysis showed the establishment of a persistent communication channel through RDP services on a non-standard port, serving as a persistent access point. The attacker then leveraged an existing user account in the system, apparently belonging to an active employee account, to escalate access to other machines on the network. Investigation further discovered that the attacker performed Credentials from Password Stores using credential dumping tools to extract password data from system storage. Additionally, System Time Discovery commands were executed to check system time, and various cyber tools were transferred into the system for continued attack operations.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1218 system binary proxy execution | ผู้โจมตีได้ใช้ System Binary Proxy Execution ผ่านเครื่องมือ certutil.exe |
| 2 | described | T1133 external remote services | มีการสร้างช่องทางการติดต่อกลับผ่านบริการ RDP ที่ยังเปิดใช้งานอยู่บนพอร์ตที่ไม่ใช่มาตรฐาน ซึ่งใช้เป็นจุดทำให้มีการเข้าถึงระบบอย่างต่อเนื่อง |
| 3 | described | T1078 valid accounts | ผู้โจมตีได้ใช้บัญชีผู้ใช้ที่มีอยู่แล้วในระบบซึ่งดูเหมือนว่าเป็นบัญชีพนักงานที่ยังคงใช้งานอยู่ เพื่อเพิ่มสิทธิการเข้าถึง |
| 4 | named | T1555 credentials from password stores | ผู้โจมตีได้ทำการ Credentials from Password Stores โดยใช้เครื่องมือประเภท credential dumping |
| 5 | named | T1124 system time discovery | พบการเรียกใช้คำสั่ง System Time Discovery เพื่อตรวจสอบเวลาระบบ |
| 6 | named | T1105 ? | การถ่ายโอนเครื่องมือไซเบอร์ต่างๆ เข้ามาในระบบเพื่อใช้ในการโจมตีต่อเนื่อง |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_005  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานคร ได้รับแจ้งเบาะแสจากพนักงานว่าบัญชี email ของผู้บริหารถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการสอบสวนเบื้องต้น พบว่าผู้โจมตีได้ติดต่อบริษัทโทรศัพท์เคลื่อนที่โดยอ้างว่าเป็นเจ้าของหมายเลขโทรศัพท์ และขอให้โอนบริการไปยังซิมการ์ดใหม่ ต่อมาจากการตรวจสอบ log server พบว่าการเข้าถึงบัญชีมาจากที่อยู่ IP ที่ผ่าน proxy หลายชั้น ในขั้นตอนต่อไป ผู้โจมตีได้ทำการส่ง SMS ที่มีลิงก์ปลอมเพื่อให้ผู้บริหารคลิกและป้อนรหัส OTP ที่ได้รับจากข้อความสั้นบนซิมการ์ดใหม่ของตัวเอง ซึ่งเป็นการตัดขาดการยืนยันตัวตนแบบสองชั้นของระบบ

*EN:* On 22 February 2569, a financial services company in Bangkok received notification from an employee that an executive's email account had been accessed without authorization. Preliminary investigation revealed that the attacker had contacted a mobile telephone service provider, claiming to be the legitimate account holder, and requested service transfer to a new SIM card. Subsequently, server log analysis showed that account access originated from an IP address routed through proxy infrastructure. In the subsequent phase, the attacker sent SMS messages containing fraudulent links to the executive, prompting them to click and enter the OTP code received in text messages on the attacker's newly obtained SIM card, thereby circumventing the system's two-factor authentication mechanism.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1451 sim card swap | ผู้โจมตีได้ติดต่อบริษัทโทรศัพท์เคลื่อนที่โดยอ้างว่าเป็นเจ้าของหมายเลขโทรศัพท์ และขอให้โอนบริการไปยังซิมการ์ดใหม่ |
| 2 | named | T1090 ? | การเข้าถึงบัญชีมาจากที่อยู่ IP ที่ผ่าน proxy หลายชั้น |
| 3 | described | T1111 multi-factor authentication interception | ผู้โจมตีได้ทำการส่ง SMS ที่มีลิงก์ปลอมเพื่อให้ผู้บริหารคลิกและป้อนรหัส OTP ที่ได้รับจากข้อความสั้นบนซิมการ์ดใหม่ของตัวเอง |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_006  (source group: (previous run) )

**AUTO-FLAGS: step 1: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบเซิร์ฟเวอร์หลักของฝ่ายบัญชีถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ของระบบ Active Directory พบว่าบัญชีพนักงานชั้นปลายชื่อ Somchai.Tiwakul ซึ่งเป็นเจ้าหน้าที่ IT ระดับ junior ได้ถูกนำมาใช้เข้าสู่ระบบจากที่อยู่ IP ต่างประเทศหลายครั้ง และมีการเข้าถึงทรัพยากรเครือข่ายที่อยู่นอกขอบเขตสิทธิ์ของบัญชีนั้น ต่อมาจากการตรวจสอบพยานหลักฐานพบว่าผู้โจมตีได้ใช้บัญชีดังกล่าวในการเข้าถึงเซิร์ฟเวอร์ RDP ของฝ่ายบัญชีและบังคับให้มีการเชื่อมต่อจากอีกเครื่องคอมพิวเตอร์ที่อยู่ภายในเครือข่าย จากนั้นระบบตรวจสอบการเข้าถึงพบการถ่ายโอนไฟล์ขนาดใหญ่ผ่าน SFTP ไปยังเซิร์ฟเวอร์ภายนอก รวมถึงการดาวน์โหลด utility tools หลากหลายชนิดเช่น netcat และ mimikatz ลงในโฟลเดอร์ temp ของระบบ

*EN:* On 22 February 2569, a logistics service company in Samut Prakan Province reported unauthorized access to its main accounting department server. Log examination of the Active Directory system revealed that an employee account named Somchai.Tiwakul, a junior-level IT officer, had been used to log in from multiple foreign IP addresses and accessed network resources outside the account's authorization scope. Further forensic investigation found that the attacker had used this account to access the accounting department's RDP server and forced connections from another computer within the network. Subsequently, system monitoring detected large file transfers via SFTP to an external server, as well as downloads of various utility tools such as netcat and mimikatz to the system's temp folder.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | บัญชีพนักงานชั่นปลายชื่อ Somchai.Tiwakul ซึ่งเป็นเจ้าหน้าที่ IT ระดับ junior ได้ถูกนำมาใช้เข้าสู่ระบบจากที่อยู่ IP ต่างประเทศหลายครั้ง และมีการเข้าถึงทรัพยากรเครือข่ายที่อยู่นอกขอบเขตสิทธิ์ของบัญชีนั้น |
| 2 | described | T1210 ? | ผู้โจมตีได้ใช้บัญชีดังกล่าวในการเข้าถึงเซิร์ฟเวอร์ RDP ของฝ่ายบัญชีและบังคับให้มีการเชื่อมต่อจากอีกเครื่องคอมพิวเตอร์ที่อยู่ภายในเครือข่าย |
| 3 | described | T1105 ? | การถ่ายโอนไฟล์ขนาดใหญ่ผ่าน SFTP ไปยังเซิร์ฟเวอร์ภายนอก รวมถึงการดาวน์โหลด utility tools หลากหลายชนิดเช่น netcat และ mimikatz ลงในโฟลเดอร์ temp ของระบบ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_007  (source group: (previous run) )

**AUTO-FLAGS: step 1: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบ workstation ของเจ้าหน้าที่ฝ่ายบัญชีถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log และ endpoint detection พบว่าผู้โจมตีได้ส่ง payload ผ่านทาง email attachment และดำเนินการรันคำสั่งชุดหนึ่งผ่าน PowerShell เพื่อดাวน์โหลดและรันไฟล์เพิ่มเติม ต่อมาจากการวิเคราะห์ memory dump และ process tree พบร่องรอยการฉีดโค้ดเข้าไปในโปรเซส svchost.exe ของระบบ ซึ่งเป็นการเคลื่อนไหวที่มีลักษณะเพื่อให้ได้สิทธิการเข้าถึงระดับสูงขึ้น จากนั้นผู้วิเคราะห์พบว่าไฟล์ต่างๆ ที่เกี่ยวข้องกับการโจมตีได้ถูกเข้ารหัสและซ่อนไว้ภายในโฟลเดอร์ระบบ โดยมีชื่อไฟล์ที่ถูกปลอมแปลงให้ดูเหมือนไฟล์ระบบปกติ เพื่อหลีกเลี่ยงการตรวจพบ

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to a staff member's accounting department workstation. Upon examination of logs and endpoint detection, it was found that the attacker sent a payload via email attachment and executed a series of commands through PowerShell to download and run additional files. Subsequently, analysis of memory dumps and process trees revealed evidence of code injection into the system's svchost.exe process, a behaviour consistent with privilege elevation attempts. Thereafter, analysts discovered that files associated with the attack had been encrypted and concealed within system directories, with filenames spoofed to resemble normal system files in order to evade detection.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1059 ? | ดำเนินการรันคำสั่งชุดหนึ่งผ่าน PowerShell เพื่อดาวน์โหลดและรันไฟล์เพิ่มเติม |
| 2 | described | T1055 ? | พบร่องรอยการฉีดโค้ดเข้าไปในโปรเซส svchost.exe ของระบบ ซึ่งเป็นการเคลื่อนไหวที่มีลักษณะเพื่อให้ได้สิทธิการเข้าถึงระดับสูงขึ้น |
| 3 | described | T1027 ? | ไฟล์ต่างๆ ที่เกี่ยวข้องกับการโจมตีได้ถูกเข้ารหัสและซ่อนไว้ภายในโฟลเดอร์ระบบ โดยมีชื่อไฟล์ที่ถูกปลอมแปลงให้ดูเหมือนไฟล์ระบบปกติ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_008  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโทรคมนาคมแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้รับแจ้งเบาะแสจากแผนกเทคโนโลยีสารสนเทศว่ามีการเข้าถึงระบบเซิร์ฟเวอร์ด้วยบัญชีผู้ใช้งานที่ถูกต้องตามกฎของระบบ แต่เกิดขึ้นในเวลากลางคืนซึ่งไม่เป็นปกติ จากการตรวจสอบ log พบว่าผู้โจมตีได้ทำการค้นหาความสัมพันธ์และความเชื่อใจระหว่างโดเมนต่างๆ ในสภาพแวดล้อม Active Directory เพื่อแมปโครงสร้างเครือข่ายภายในองค์กร ต่อมาผู้โจมตีได้ติดตั้ง Remote Access Tools ชื่อ TeamViewer บนเซิร์ฟเวอร์หลักเพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่องและควบคุมจากระยะไกล จากนั้นทีมสอบสวนจึงได้ทำการอนุรักษ์หลักฐานและรายงานต่อหน่วยงานที่เกี่ยวข้อง

*EN:* On 22 February 2569, a telecommunications service company in Bangkok received notification from the IT department that there was access to a server using valid user accounts that matched system credentials, but occurring at unusual nighttime hours. Upon examination of logs, investigators found that the attacker had conducted reconnaissance of domain trust relationships and cross-domain trust configurations within the Active Directory environment to map the internal network structure of the organization. Subsequently, the attacker deployed Remote Access Tools named TeamViewer on the primary server to maintain persistent access and control the system remotely. The investigation team then preserved digital evidence and reported the matter to relevant authorities.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | มีการเข้าถึงระบบเซิร์ฟเวอร์ด้วยบัญชีผู้ใช้งานที่ถูกต้องตามกฎของระบบ แต่เกิดขึ้นในเวลากลางคืนซึ่งไม่เป็นปกติ |
| 2 | described | T1482 domain trust discovery | ผู้โจมตีได้ทำการค้นหาความสัมพันธ์และความเชื่อใจระหว่างโดเมนต่างๆ ในสภาพแวดล้อม Active Directory เพื่อแมปโครงสร้างเครือข่ายภายในองค์กร |
| 3 | named | T1219 remote access tools | ผู้โจมตีได้ติดตั้ง Remote Access Tools ชื่อ TeamViewer บนเซิร์ฟเวอร์หลักเพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่องและควบคุมจากระยะไกล |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_009  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบเซิร์ฟเวอร์ของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log และหลักฐานดิจิทัลพบว่า ผู้โจมตีได้ใช้ Process Injection เพื่อฝังโค้ดอันตรายลงในโปรเซสของระบบปฏิบัติการที่ทำงานในสิทธิ์สูง ต่อมา ผู้โจมตีได้ดำเนินการใช้ประโยชน์จากช่องโหว่ในไลบรารีระบบเพื่อเพิ่มสิทธิ์การเข้าถึงและขยายพื้นที่ควบคุมไปยังบัญชีผู้ใช้อื่น ๆ ในเครือข่ายเดียวกัน จากนั้น ระบบตรวจจับพบการส่งข้อมูลออกจากเซิร์ฟเวอร์ไปยังที่อยู่ IP ต่างประเทศ พร้อมกับการดาวน์โหลดเครื่องมือเพิ่มเติมและสคริปต์ที่ไม่ได้รับอนุญาตเข้ามาในระบบ สุดท้าย ทีม IT ได้隔离 เซิร์ฟเวอร์ที่ได้รับผลกระทบและเริ่มการสอบสวนอย่างเต็มรูปแบบ

*EN:* On 22 February 2569, an information technology service company in Samut Prakan Province reported unauthorized access to their server system. From examination of logs and digital evidence, it was found that the attacker used Process Injection to embed malicious code into system processes running with elevated privileges. Subsequently, the attacker exploited a vulnerability in a system library to escalate access rights and extend control to other user accounts within the same network. Afterward, the system detected data exfiltration from the server to foreign IP addresses, accompanied by the download of unauthorized tools and scripts into the system. Finally, the IT team isolated the affected server and initiated a full investigation.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1055 ? | ผู้โจมตีได้ใช้ Process Injection เพื่อฝังโค้ดอันตรายลงในโปรเซสของระบบปฏิบัติการที่ทำงานในสิทธิ์สูง |
| 2 | described | T1068 ? | ผู้โจมตีได้ดำเนินการใช้ประโยชน์จากช่องโหว่ในไลบรารีระบบเพื่อเพิ่มสิทธิ์การเข้าถึงและขยายพื้นที่ควบคุมไปยังบัญชีผู้ใช้อื่น ๆ ในเครือข่ายเดียวกัน |
| 3 | described | T1105 ? | ระบบตรวจจับพบการส่งข้อมูลออกจากเซิร์ฟเวอร์ไปยังที่อยู่ IP ต่างประเทศ พร้อมกับการดาวน์โหลดเครื่องมือเพิ่มเติมและสคริปต์ที่ไม่ได้รับอนุญาตเข้ามาในระบบ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_010  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการการเงินแห่งหนึ่งในจังหวัดกรุงเทพ แจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้เรียกใช้ PowerShell script โดยตรงผ่าน Native API เพื่อดำเนินการบนระบบเป้าหมาย ต่อมาจากการวิเคราะห์ registry hive พบว่ามีการแก้ไขค่า Run key ในส่วน HKLM\Software\Microsoft\Windows\CurrentVersion เพื่อให้ malware โหลดตัวเองขึ้นมาทุกครั้งที่ระบบบูต จากนั้นผู้โจมตีได้ใช้ Valid Accounts ของเจ้าหน้าที่ IT ท้องถิ่นเพื่อขยายสิทธิการเข้าถึง สุดท้ายจากการตรวจสอบ file system พบไฟล์ที่มีชื่อที่ซ่อนความเป็นจริงและมีส่วนขยาย double extension ที่ถูกสร้างขึ้นในโฟลเดอร์ temp จากการติดตามเนตเวิร์ก traffic พบว่าเซิร์ฟเวอร์ได้ส่งคำสั่ง net view และ nslookup เพื่อทำการค้นหาเครื่องคอมพิวเตอร์อื่นๆ ในเครือข่ายภายใน และในระยะสุดท้ายได้มีการถ่ายโอน executable file ขนาด 8.5 MB ไปยังเครื่องสถานีงานที่อยู่ในเซกเมนต์เดียวกัน

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to its primary server. Log analysis revealed the attacker invoked PowerShell script directly via Native API to execute commands on the target system. Subsequent examination of the registry hive showed modifications to the Run key under HKLM\Software\Microsoft\Windows\CurrentVersion to enable malware persistence at boot. The attacker then leveraged Valid Accounts belonging to a local IT staff member to escalate access privileges. File system inspection uncovered files with misleading names and double extensions created in the temp folder. Network traffic analysis showed the server issued net view and nslookup commands to enumerate other computers on the internal network. Finally, an 8.5 MB executable file was transferred to a workstation in the same network segment.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1106 ? | เรียกใช้ PowerShell script โดยตรงผ่าน Native API เพื่อดำเนินการบนระบบเป้าหมาย |
| 2 | described | T1112 modify registry | มีการแก้ไขค่า Run key ในส่วน HKLM\Software\Microsoft\Windows\CurrentVersion เพื่อให้ malware โหลดตัวเองขึ้นมาทุกครั้งที่ระบบบูต |
| 3 | named | T1078 valid accounts | ผู้โจมตีได้ใช้ Valid Accounts ของเจ้าหน้าที่ IT ท้องถิ่น |
| 4 | described | T1027 ? | พบไฟล์ที่มีชื่อที่ซ่อนความเป็นจริงและมีส่วนขยาย double extension ที่ถูกสร้างขึ้นในโฟลเดอร์ temp |
| 5 | described | T1018 remote system discovery | เซิร์ฟเวอร์ได้ส่งคำสั่ง net view และ nslookup เพื่อทำการค้นหาเครื่องคอมพิวเตอร์อื่นๆ ในเครือข่ายภายใน |
| 6 | described | T1105 ? | มีการถ่ายโอน executable file ขนาด 8.5 MB ไปยังเครื่องสถานีงานที่อยู่ในเซกเมนต์เดียวกัน |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_011  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการจัดการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบเซิร์ฟเวอร์ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ทำการประมวลผลคำสั่งบนระบบปฏิบัติการ Linux ด้วยสิทธิของผู้ใช้ทั่วไป แล้วใช้ประโยชน์จากช่องโหว่ในเคอร์เนล kernel exploit เพื่อยกระดับสิทธิ์การเข้าถึงขึ้นเป็น root ต่อมาผู้โจมตีได้ทำการรวบรวมไฟล์ข้อมูลสำคัญจำนวนมากจากเซิร์ฟเวอร์ฐานข้อมูล และทำการบีบอัดไฟล์เหล่านั้นลงในไฟล์ archive ขนาด 47 GB สำหรับการส่งออกข้อมูล จากนั้นผู้โจมตีได้ตั้งค่าการเชื่อมต่อ non-standard port ไปยังเซิร์ฟเวอร์ของตนเองผ่านพอร์ต 8847 เพื่อใช้ในการสั่งการและควบคุมระบบที่ถูกบุกรุก สุดท้ายจึงทำการส่งข้อมูลที่บีบอัดแล้วออกไปจากระบบ

*EN:* On 22 February 2569, a private logistics management company in Samut Prakan Province reported unauthorized access to its server system. Upon examination of logs, investigators found that the attacker executed commands on the Linux operating system with standard user privileges, then exploited a kernel vulnerability to escalate privileges to root level. Subsequently, the attacker collected numerous critical data files from the database server and compressed them into a 47 GB archive file for exfiltration. The attacker then configured a non-standard port connection to their own server via port 8847 for command and control of the compromised system. Finally, the compressed data was transmitted out of the system.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1068 ? | ใช้ประโยชน์จากช่องโหว่ในเคอร์เนล kernel exploit เพื่อยกระดับสิทธิ์การเข้าถึงขึ้นเป็น root |
| 2 | described | T1560 archive collected data | ทำการรวบรวมไฟล์ข้อมูลสำคัญจำนวนมากจากเซิร์ฟเวอร์ฐานข้อมูล และทำการบีบอัดไฟล์เหล่านั้นลงในไฟล์ archive ขนาด 47 GB |
| 3 | named | T1571 non-standard port | ตั้งค่าการเชื่อมต่อ non-standard port ไปยังเซิร์ฟเวอร์ของตนเองผ่านพอร์ต 8847 |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_012  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโทรคมนาคมแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้แจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ระบบพบว่าผู้โจมตีได้เชื่อมต่อผ่านทาง SSH port 22 ด้วยข้อมูลประจำตัวที่ขโมยมาจากพนักงานระดับกลาง และยังคงรักษาการเข้าถึงโดยสร้าง backdoor account ที่ซ่อนไว้ในระบบ ต่อมาผู้โจมตีได้ทำการ process injection เพื่อให้สิทธิ์เพิ่มขึ้นเป็น root user ผ่านเครื่องมือที่ฝังตัวอยู่ในหน่วยความจำ จากนั้นผู้โจมตีได้ติดตั้ง network sniffing tool บนเซิร์ฟเวอร์เพื่อจับภาพการสื่อสารของเครือข่ายภายในและเก็บข้อมูลการยืนยันตัวตนของผู้ใช้งานอื่น สุดท้ายผู้โจมตีได้ส่งเครื่องมือโจมตีเพิ่มเติมไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่ายเดียวกัน เพื่อขยายขอบเขตของการบุกรุก

*EN:* On 22 February 2569, a telecommunications service company in Bangkok reported unauthorized access to its main server. Log examination revealed that the attacker connected via SSH port 22 using stolen credentials from a mid-level employee and maintained access by creating a hidden backdoor account in the system. Subsequently, the attacker performed process injection to escalate privileges to root user through tools embedded in memory. The attacker then installed network sniffing tools on the server to capture internal network communications and collect authentication data from other users. Finally, the attacker transferred additional attack tools to other servers on the same network to expand the scope of the intrusion.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1133 external remote services | สร้าง backdoor account ที่ซ่อนไว้ในระบบ |
| 2 | named | T1055 ? | ทำการ process injection เพื่อให้สิทธิ์เพิ่มขึ้นเป็น root user |
| 3 | named | T1040 network sniffing | ติดตั้ง network sniffing tool บนเซิร์ฟเวอร์เพื่อจับภาพการสื่อสารของเครือข่าย |
| 4 | described | T1570 lateral tool transfer | ส่งเครื่องมือโจมตีเพิ่มเติมไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่ายเดียวกัน |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_013  (source group: (previous run) )

> เมื่อวันที่ 23 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการจัดการลอจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่า ระบบสารสนเทศของบริษัทได้รับความเสียหายจากการโจมตี จากการตรวจสอบพยานหลักฐานดิจิทัลพบว่า ผู้โจมตีได้เข้าถึงระบบผ่านช่องทางการอัปเดตซอฟต์แวร์ของบริษัทจัดหาวัสดุอุปกรณ์ที่บริษัทเสียหายใช้งานอยู่ ซึ่งมีการแทรกโค้ดอันตรายเข้าไปในแพคเกจการติดตั้ง ต่อมา จากการวิเคราะห์กิจกรรมในระบบพบว่า ตั้งแต่การเข้าถึงเป็นต้นมา ผู้โจมตีได้ทำการจับภาพหน้าจอของเครื่องคอมพิวเตอร์ของพนักงานเป็นระยะเวลาต่อเนื่อง เพื่อเก็บรวบรวมข้อมูลที่แสดงบนจอ รวมถึงข้อมูลการเข้าสู่ระบบและเอกสารทางธุรกิจ จากนั้น จากการติดตามการสื่อสารของตัวอนุมาลแวร์พบว่า ผู้โจมตีได้ใช้ Fallback Channels เพื่อรักษาการเชื่อมต่อกับระบบที่ติดเชื้อ โดยมีการสลับไปมาระหว่างเซิร์ฟเวอร์ Command and Control หลายแห่งเมื่อช่องทางการสื่อสารหลักถูกขัดขวาง

*EN:* On 23 February 2569, a private logistics management company in Samut Prakan Province reported damage to its information system from a cyberattack. Digital forensic examination revealed that the attacker gained access through the software update channel of a supply vendor used by the affected company, with malicious code injected into the installation package. Subsequently, analysis of system activity showed that from the point of access onward, the attacker captured screenshots of employee workstation displays continuously to collect information displayed on screen, including login credentials and business documents. Thereafter, monitoring of malware communications revealed that the attacker employed Fallback Channels to maintain connection with the infected system, switching between multiple Command and Control servers when the primary communication channel was blocked.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1195 ? | ผู้โจมตีได้เข้าถึงระบบผ่านช่องทางการอัปเดตซอฟต์แวร์ของบริษัทจัดหาวัสดุอุปกรณ์ที่บริษัทเสียหายใช้งานอยู่ ซึ่งมีการแทรกโค้ดอันตรายเข้าไปในแพคเกจการติดตั้ง |
| 2 | described | T1113 ? | ผู้โจมตีได้ทำการจับภาพหน้าจอของเครื่องคอมพิวเตอร์ของพนักงานเป็นระยะเวลาต่อเนื่อง เพื่อเก็บรวบรวมข้อมูลที่แสดงบนจอ |
| 3 | named | T1008 fallback channels | ผู้โจมตีได้ใช้ Fallback Channels เพื่อรักษาการเชื่อมต่อกับระบบที่ติดเชื้อ โดยมีการสลับไปมาระหว่างเซิร์ฟเวอร์ Command and Control หลายแห่งเมื่อช่องทางการสื่อสารหลักถูกขัดขวาง |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_014  (source group: (previous run) )

**AUTO-FLAGS: step 4: described cue names the technique (software deployment tools)**

> เมื่อวันที่ 12 กุมภาพันธ์ 2569 บริษัทเอกชนแห่งหนึ่งในจังหวัดสมุทรปราการที่ประกอบธุรกิจด้านการจัดการสินค้าคงคลัง ได้รับแจ้งเบาะแสจากผู้ดูแลระบบว่าพบกิจกรรมที่ผิดปกติในบัญชีพนักงานส่วนกลาง จากการตรวจสอบ log พบว่าบัญชีดังกล่าวถูกใช้งานเพื่อเข้าสู่เซิร์ฟเวอร์หลัก และมีการเปิดใช้งานในเวลากลางคืน ซึ่งไม่สอดคล้องกับรูปแบบการทำงานปกติ ต่อมาผู้โจมตีได้ทำการ process injection เพื่อแฝงตัวของโปรแกรมอันตรายไว้ในกระบวนการระบบที่ถูกต้องตามกฎหมาย จากนั้นทำการ remote system discovery เพื่อค้นหาเซิร์ฟเวอร์และอุปกรณ์อื่นๆ ที่เชื่อมต่อในเครือข่ายภายใน สุดท้ายผู้โจมตีใช้เครื่องมือ software deployment tools ที่มีอยู่ในสภาพแวดล้อมการจัดการ IT เพื่อแพร่กระจายมัลแวร์ไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่าย

*EN:* On 12 February 2569, a private logistics management company in Samut Prakan Province received an alert from a system administrator regarding suspicious activity detected on a shared employee account. Upon examining the logs, investigators found that the account was being used to access the main server at unusual hours inconsistent with normal work patterns. Subsequently, the attacker performed process injection to conceal malicious code within legitimate system processes. The attacker then conducted remote system discovery to identify other servers and devices connected to the internal network. Finally, the attacker leveraged software deployment tools already present in the IT management environment to distribute malware across additional servers on the network.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | บัญชีพนักงานส่วนกลาง จากการตรวจสอบ log พบว่าบัญชีดังกล่าวถูกใช้งานเพื่อเข้าสู่เซิร์ฟเวอร์หลัก และมีการเปิดใช้งานในเวลากลางคืน ซึ่งไม่สอดคล้องกับรูปแบบการทำงานปกติ |
| 2 | named | T1055 ? | ผู้โจมตีได้ทำการ process injection เพื่อแฝงตัวของโปรแกรมอันตรายไว้ในกระบวนการระบบที่ถูกต้องตามกฎหมาย |
| 3 | named | T1018 remote system discovery | ทำการ remote system discovery เพื่อค้นหาเซิร์ฟเวอร์และอุปกรณ์อื่นๆ ที่เชื่อมต่อในเครือข่ายภายใน |
| 4 | described | T1072 software deployment tools | ใช้เครื่องมือ software deployment tools ที่มีอยู่ในสภาพแวดล้อมการจัดการ IT เพื่อแพร่กระจายมัลแวร์ไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่าย |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_015  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการได้รับแจ้งเบาะแสว่าระบบ ERP ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log เซิร์ฟเวอร์พบว่าผู้โจมตีได้ใช้ Web Service ที่เปิดให้บริการสาธารณะเพื่อหลีกเลี่ยงการตรวจจับจากระบบป้องกัน ต่อมาจากการวิเคราะห์ traffic ระบุว่าผู้โจมตีได้ส่งคำขอ API ไปยังเซิร์ฟเวอร์ authentication และดักจับ OTP ที่ส่งไปยังโทรศัพท์มือถือของพนักงานในเวลาจริง จากนั้นผู้โจมตีได้ใช้ข้อมูล credential และรหัส OTP ที่ดักจับได้เข้าสู่ระบบสำเร็จและดาวน์โหลดไฟล์ข้อมูลลูกค้า จากการติดตามการไหลของข้อมูลพบว่าไฟล์ที่มีขนาด 2.3 GB ได้ถูกส่งออกไปยังเซิร์ฟเวอร์ C2 ที่อยู่นอกประเทศผ่านช่องทาง HTTPS ซึ่งปลายทางอยู่ในเครือข่ายที่ไม่สามารถติดตามได้

*EN:* On 22 February 2569, a logistics service company in Samut Prakan province received intelligence that its ERP system had been accessed without authorization. Log server analysis revealed that the attacker used a Web Service exposed to the public to evade detection by the security system. Subsequently, traffic analysis identified that the attacker sent API requests to the authentication server and intercepted the OTP sent to an employee's mobile phone in real time. The attacker then successfully logged in using the captured credentials and OTP code and downloaded customer data files. Data flow tracking showed that a 2.3 GB file was exfiltrated to a C2 server outside the country via an HTTPS channel with an untraceable endpoint.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1102 ? | ผู้โจมตีได้ใช้ Web Service ที่เปิดให้บริการสาธารณะเพื่อหลีกเลี่ยงการตรวจจับจากระบบป้องกัน |
| 2 | described | T1111 multi-factor authentication interception | ผู้โจมตีได้ส่งคำขอ API ไปยังเซิร์ฟเวอร์ authentication และดักจับ OTP ที่ส่งไปยังโทรศัพท์มือถือของพนักงานในเวลาจริง |
| 3 | described | T1041 ? | ไฟล์ที่มีขนาด 2.3 GB ได้ถูกส่งออกไปยังเซิร์ฟเวอร์ C2 ที่อยู่นอกประเทศผ่านช่องทาง HTTPS |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_016  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบเซิร์ฟเวอร์ของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ของระบบ Windows พบว่าผู้โจมตีได้สร้างและดำเนินการ scheduled task ผ่าน bitsadmin.exe เพื่อเรียกใช้สคริปต์ที่ซ่อนอยู่ในเวลากลางคืน ซึ่งเป็นวิธีการที่หลีกเลี่ยงการตรวจจับจากระบบป้องกันมาตรฐาน ต่อมาจากการวิเคราะห์ memory dump และ registry พบร่องรอยของการสแกนและแจงนับไฟล์ในโฟลเดอร์ต่างๆ เช่น AppData, Temp และ Downloads ของผู้ใช้หลายคน ซึ่งแสดงให้เห็นว่าผู้โจมตีได้ค้นหาข้อมูลที่เก็บไว้ในเครื่องเป้าหมาย จากนั้นจากการตรวจสอบเพิ่มเติมพบว่ามีการถ่ายโอนไฟล์ที่มีขนาดใหญ่ผ่านช่องทาง HTTP ไปยังเซิร์ฟเวอร์ที่อยู่ในต่างประเทศ พร้อมกับการดาวน์โหลดเครื่องมือ penetration testing ที่ไม่ได้รับอนุญาต ซึ่งบ่งชี้ว่าผู้โจมตีได้ขยายการเข้าถึงไปยังระบบอื่นๆ ในเครือข่ายภายในของบริษัท

*EN:* On 22 February 2569, a logistics services company in Samut Prakan province reported unauthorized access to its server systems. Upon examination of Windows system logs, investigators found that the attacker had created and executed scheduled tasks via bitsadmin.exe to run hidden scripts during nighttime hours, a method designed to evade standard detection systems. Subsequently, analysis of memory dumps and registry entries revealed traces of file scanning and enumeration in various user folders including AppData, Temp, and Downloads, indicating the attacker searched for data stored on the target machine. Further investigation discovered large file transfers over HTTP channels to foreign servers, accompanied by downloads of unauthorized penetration testing tools, suggesting the attacker had expanded access to other systems within the company's internal network.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1197 bits jobs | สร้างและดำเนินการ scheduled task ผ่าน bitsadmin.exe เพื่อเรียกใช้สคริปต์ที่ซ่อนอยู่ในเวลากลางคืน ซึ่งเป็นวิธีการที่หลีกเลี่ยงการตรวจจับจากระบบป้องกันมาตรฐาน |
| 2 | described | T1680 local storage discovery | การสแกนและแจงนับไฟล์ในโฟลเดอร์ต่างๆ เช่น AppData, Temp และ Downloads ของผู้ใช้หลายคน ซึ่งแสดงให้เห็นว่าผู้โจมตีได้ค้นหาข้อมูลที่เก็บไว้ในเครื่องเป้าหมาย |
| 3 | described | T1105 ? | มีการถ่ายโอนไฟล์ที่มีขนาดใหญ่ผ่านช่องทาง HTTP ไปยังเซิร์ฟเวอร์ที่อยู่ในต่างประเทศ พร้อมกับการดาวน์โหลดเครื่องมือ penetration testing ที่ไม่ได้รับอนุญาต |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_017  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนแห่งหนึ่งในจังหวัดสมุทรปราการที่ประกอบธุรกิจด้านการจัดการโลจิสติกส์ได้แจ้งความว่าระบบเว็บแอปพลิเคชันของบริษัท (ระบบจัดการคำสั่งซื้อออนไลน์) ถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Exploit Public-Facing Application ผ่านช่องโหว่ในหน้าเข้าสู่ระบบ และสามารถเข้าถึงเซิร์ฟเวอร์หลักได้สำเร็จ ต่อมา ผู้โจมตีทำการ Ingress Tool Transfer โดยนำเครื่องมือตรวจสอบระบบและสคริปต์ automation เข้ามาในสภาพแวดล้อมเครือข่ายภายในเพื่อเตรียมการเคลื่อนไหวต่อไป จากนั้นจากการตรวจสอบพยานหลักฐานดิจิทัลพบว่าผู้โจมตีได้ดำเนินการค้นหาและคัดลอกข้อมูลจากเครื่องคอมพิวเตอร์เซิร์ฟเวอร์ เช่น ฐานข้อมูลลูกค้า ข้อมูลการเงิน และเอกสารอื่นๆ ที่เก็บไว้ในระบบไฟล์ภายในไปยังพื้นที่การทำงานชั่วคราวเพื่อเตรียมการส่งออกข้อมูล

*EN:* On 22 February 2569, a private logistics management company in Samut Prakan Province reported that its web application system (online order management system) was accessed without authorization. From log analysis, it was found that the attacker used Exploit Public-Facing Application through a vulnerability in the login page and successfully gained access to the main server. Subsequently, the attacker performed Ingress Tool Transfer by introducing system reconnaissance tools and automation scripts into the internal network environment to prepare for further lateral movement. Investigation of digital evidence then revealed that the attacker conducted searches and copied data from server computers, including customer databases, financial information, and other documents stored in the internal file system to a temporary working area in preparation for data exfiltration.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1190 exploit public-facing application | ผู้โจมตีได้ใช้ Exploit Public-Facing Application ผ่านช่องโหว่ในหน้าเข้าสู่ระบบ |
| 2 | named | T1105 ? | ผู้โจมตีทำการ Ingress Tool Transfer โดยนำเครื่องมือตรวจสอบระบบและสคริปต์ automation เข้ามาในสภาพแวดล้อมเครือข่ายภายใน |
| 3 | described | T1005 ? | ผู้โจมตีได้ดำเนินการค้นหาและคัดลอกข้อมูลจากเครื่องคอมพิวเตอร์เซิร์ฟเวอร์ เช่น ฐานข้อมูลลูกค้า ข้อมูลการเงิน และเอกสารอื่นๆ ที่เก็บไว้ในระบบไฟล์ภายใน |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_018  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกบุกรุก จากการตรวจสอบ log พบว่าผู้โจมตีได้ฝังโค้ดอันตรายลงในกระบวนการ svchost.exe เพื่อหลีกเลี่ยงการตรวจสอบของ antivirus ต่อมาผู้โจมตีใช้ Remote Services ผ่านโปรโตคอล RDP เพื่อเข้าถึงเซิร์ฟเวอร์อื่นๆ ในเครือข่ายภายใน จากนั้นทำการ Data from Local System โดยดึงข้อมูลจากไฟล์ฐานข้อมูลและบัญชีผู้ใช้ที่เก็บไว้ในระบบ สุดท้ายผู้โจมตีทำการ Ingress Tool Transfer เพื่อดาวน์โหลดเครื่องมือสำหรับการโจมตีเพิ่มเติมจากเซิร์ฟเวอร์ภายนอกมายังเครื่องที่ถูกบุกรุก

*EN:* On 22 February 2569, a private financial services company in Bangkok reported that its primary server had been compromised. Upon examination of the logs, investigators found that the attacker had injected malicious code into the svchost.exe process to evade antivirus detection. Subsequently, the attacker used Remote Services via RDP protocol to access other servers within the internal network. The attacker then performed Data from Local System by extracting database files and user account credentials stored on the system. Finally, the attacker conducted Ingress Tool Transfer by downloading additional attack tools from an external server onto the compromised machine.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1055 ? | ผู้โจมตีได้ฝังโค้ดอันตรายลงในกระบวนการ svchost.exe เพื่อหลีกเลี่ยงการตรวจสอบของ antivirus |
| 2 | named | T1021 remote services | ผู้โจมตีใช้ Remote Services ผ่านโปรโตคอล RDP เพื่อเข้าถึงเซิร์ฟเวอร์อื่นๆ ในเครือข่ายภายใน |
| 3 | named | T1005 ? | ทำการ Data from Local System โดยดึงข้อมูลจากไฟล์ฐานข้อมูลและบัญชีผู้ใช้ที่เก็บไว้ในระบบ |
| 4 | named | T1105 ? | ผู้โจมตีทำการ Ingress Tool Transfer เพื่อดาวน์โหลดเครื่องมือสำหรับการโจมตีเพิ่มเติมจากเซิร์ฟเวอร์ภายนอก |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_019  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการจัดการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบเซิร์ฟเวอร์ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ของอุปกรณ์เครือข่ายพบว่า ผู้โจมตีได้ทำการ network service discovery เพื่อค้นหาเซิร์ฟเวอร์ที่เปิดพอร์ตและบริการต่างๆ บนระบบเครือข่ายภายในบริษัท ต่อมา จากการตรวจสอบพบการเข้าถึงไฟล์ข้อมูลลูกค้าและใบสั่งซื้อจำนวนมากอย่างผิดปกติ โดยมีการคัดลอกข้อมูลเป็นจำนวนมากในระยะเวลาสั้นๆ สุดท้าย จากการวิเคราะห์ traffic ของระบบเครือข่ายพบว่า ข้อมูลที่ถูกเก็บรวบรวมได้ถูกส่งออกไปยังเซิร์ฟเวอร์ต่างประเทศผ่านช่องทางการสื่อสารที่ผู้โจมตีสร้างขึ้นเพื่อควบคุมและสั่งการ

*EN:* On 22 February 2569, a private logistics management company in Samut Prakan Province reported unauthorized access to its server systems. From examination of network device logs, it was found that the attacker performed network service discovery to identify servers with open ports and running services on the company's internal network. Subsequently, investigation revealed abnormal access to customer files and purchase orders in large quantities, with data being copied in significant volume over a short timeframe. Finally, analysis of network traffic showed that the collected data was transmitted to foreign servers through a command-and-control channel established by the attacker.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1046 network service discovery | ผู้โจมตีได้ทำการ network service discovery เพื่อค้นหาเซิร์ฟเวอร์ที่เปิดพอร์ตและบริการต่างๆ บนระบบเครือข่ายภายในบริษัท |
| 2 | described | T1119 automated collection | จากการตรวจสอบพบการเข้าถึงไฟล์ข้อมูลลูกค้าและใบสั่งซื้อจำนวนมากอย่างผิดปกติ โดยมีการคัดลอกข้อมูลเป็นจำนวนมากในระยะเวลาสั้นๆ |
| 3 | described | T1041 ? | ข้อมูลที่ถูกเก็บรวบรวมได้ถูกส่งออกไปยังเซิร์ฟเวอร์ต่างประเทศผ่านช่องทางการสื่อสารที่ผู้โจมตีสร้างขึ้นเพื่อควบคุมและสั่งการ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_020  (source group: (previous run) )

**AUTO-FLAGS: step 1: described cue names the technique (windows management instrumentation)**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ระบบพบว่าผู้โจมตีได้เรียกใช้สคริปต์ผ่านทาง Windows Management Instrumentation เพื่อดำเนินการคำสั่งในระบบปฏิบัติการ ต่อมาผู้โจมตีได้สร้างบัญชีผู้ใช้เพิ่มเติมและตั้งค่าให้มีสิทธิ์เข้าถึงระบบเพื่อรักษาการเชื่อมต่อในระยะยาว จากการวิเคราะห์พบว่าผู้โจมตีได้ทำการ brute force เพื่อทดลองรหัสผ่านจำนวนมากกับบัญชีผู้ดูแลระบบหลายบัญชี และสำเร็จในการเข้าถึงหนึ่งบัญชี จากนั้นผู้โจมตีได้ใช้คำสั่ง system time discovery เพื่อตรวจสอบเวลาของระบบ สุดท้ายพบหลักฐานว่าข้อมูลลับของบริษัทได้ถูกส่งออกไปผ่านช่องทาง command and control และทั้งหมดถูกลบทำลายจากเซิร์ฟเวอร์ต้นทางแล้ว

*EN:* On 22 February 2569, a private information technology company in Samut Prakan Province reported unauthorized access to its primary server. From examination of system logs, investigators found that the attacker executed scripts through Windows Management Instrumentation to run commands on the operating system. Subsequently, the attacker created additional user accounts and configured them with system access privileges to maintain long-term connectivity. Analysis revealed the attacker performed brute force attempts, testing numerous passwords against multiple administrator accounts and succeeded in accessing one account. The attacker then used system time discovery commands to check the system time. Finally, evidence showed that the company's confidential data was exfiltrated over a command and control channel and subsequently destroyed from the origin server.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1047 windows management instrumentation | ผู้โจมตีได้เรียกใช้สคริปต์ผ่านทาง Windows Management Instrumentation เพื่อดำเนินการคำสั่งในระบบปฏิบัติการ |
| 2 | described | T1078 valid accounts | ผู้โจมตีได้สร้างบัญชีผู้ใช้เพิ่มเติมและตั้งค่าให้มีสิทธิ์เข้าถึงระบบเพื่อรักษาการเชื่อมต่อในระยะยาว |
| 3 | named | T1110 brute force | ผู้โจมตีได้ทำการ brute force เพื่อทดลองรหัสผ่านจำนวนมากกับบัญชีผู้ดูแลระบบหลายบัญชี |
| 4 | named | T1124 system time discovery | ผู้โจมตีได้ใช้คำสั่ง system time discovery เพื่อตรวจสอบเวลาของระบบ |
| 5 | described | T1041 ? | ข้อมูลลับของบริษัทได้ถูกส่งออกไปผ่านช่องทาง command and control |
| 6 | named | T1485 ? | ทั้งหมดถูกลบทำลายจากเซิร์ฟเวอร์ต้นทางแล้ว |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_021  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทสื่อสารด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพ ได้รับแจ้งเบาะแสจากผู้ดูแลระบบว่าพบกิจกรรมที่ผิดปกติในเครื่องสำนักงานของพนักงาน จากการตรวจสอบ log พบว่าเครื่องดังกล่าวเข้าชมเว็บไซต์ที่ถูก compromise และโหลด malicious script ลงมาทำให้เกิดการติดตั้ง backdoor ต่อมา ผู้โจมตีทำการ Account Manipulation โดยเปลี่ยนแปลงสิทธิ์ของบัญชี service account เพื่อให้มีสิทธิ์สูงขึ้น จากนั้นทำการส่ง NTLM challenge request ไปยังเครื่องหลายเครื่องในเครือข่าย เพื่อให้ผู้ใช้งานทำการพิมพ์รหัสผ่านซ้ำ และสามารถจับ hash ของข้อมูลประจำตัวไว้ได้ สุดท้าย ผู้โจมตีใช้ credentials ที่ได้มาเพื่อเรียกดูรายชื่อ shared folder และ network resource ในระบบ และทำการ transfer tools เช่น PowerShell script และ remote access utility ไปยังเครื่องอื่น ๆ ในเครือข่ายภายในบริษัท

*EN:* On 22 February 2569, a financial communications company in Bangkok received a tip from a system administrator regarding suspicious activity on an employee's workstation. Log examination revealed the machine visited a compromised website and downloaded a malicious script, resulting in backdoor installation. Subsequently, the attacker performed Account Manipulation by modifying service account privileges to elevate permissions. The attacker then sent NTLM challenge requests to multiple machines on the network, causing users to re-enter passwords and allowing credential hash capture. Finally, the attacker used the obtained credentials to enumerate shared folders and network resources on the system, and transferred tools such as PowerShell scripts and remote access utilities to other machines within the company network.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1189 ? | เครื่องดังกล่าวเข้าชมเว็บไซต์ที่ถูก compromise และโหลด malicious script ลงมาทำให้เกิดการติดตั้ง backdoor |
| 2 | named | T1098 account manipulation | ผู้โจมตีทำการ Account Manipulation โดยเปลี่ยนแปลงสิทธิ์ของบัญชี service account เพื่อให้มีสิทธิ์สูงขึ้น |
| 3 | described | T1187 forced authentication | ทำการส่ง NTLM challenge request ไปยังเครื่องหลายเครื่องในเครือข่าย เพื่อให้ผู้ใช้งานทำการพิมพ์รหัสผ่านซ้ำ และสามารถจับ hash ของข้อมูลประจำตัวไว้ได้ |
| 4 | described | T1135 network share discovery | ผู้โจมตีใช้ credentials ที่ได้มาเพื่อเรียกดูรายชื่อ shared folder และ network resource ในระบบ |
| 5 | described | T1105 ? | ทำการ transfer tools เช่น PowerShell script และ remote access utility ไปยังเครื่องอื่น ๆ ในเครือข่ายภายในบริษัท |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_022  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์หลักของหน่วยงานถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ WMI Command Line Utility เพื่อดำเนินการคำสั่งบนเครื่องคอมพิวเตอร์ของเซิร์ฟเวอร์ ต่อมาจากการวิเคราะห์ Event Viewer พบหลักฐานการเข้าสู่ระบบด้วยบัญชีผู้ใช้ที่ถูกต้องของพนักงานแผนกไอที ซึ่งบัญชีดังกล่าวมีสิทธิในการเข้าถึงโปรแกรมบริหารระบบ จากนั้นผู้โจมตีได้ทำการ Reflective Code Loading เพื่อโหลดโค้ดอันตรายลงในหน่วยความจำโดยไม่บันทึกไฟล์ลงดิสก์ สุดท้ายจากการตรวจสอบ registry และ process memory พบว่าระบบได้ทำการเรียกคำสั่งเพื่อรวบรวมข้อมูลเกี่ยวกับระบบปฏิบัติการ ตัวประมวลผล และรายการซอฟต์แวร์ที่ติดตั้งอยู่บนเครื่องเป้าหมาย

*EN:* On 22 February 2569, a private financial services company in Bangkok reported unauthorized access to its primary server system. Log analysis revealed that the attacker used WMI Command Line Utility to execute commands on the server machine. Subsequently, Event Viewer examination showed evidence of login using valid employee credentials from the IT department, which account held administrative privileges. The attacker then performed Reflective Code Loading to inject malicious code into memory without writing files to disk. Finally, registry and process memory inspection revealed that the system executed commands to gather information about the operating system, processor, and installed software inventory on the target machine.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1047 windows management instrumentation | ใช้ WMI Command Line Utility เพื่อดำเนินการคำสั่งบนเครื่องคอมพิวเตอร์ |
| 2 | described | T1078 valid accounts | พบหลักฐานการเข้าสู่ระบบด้วยบัญชีผู้ใช้ที่ถูกต้องของพนักงานแผนกไอที ซึ่งบัญชีดังกล่าวมีสิทธิในการเข้าถึงโปรแกรมบริหารระบบ |
| 3 | named | T1620 reflective code loading | ทำการ Reflective Code Loading เพื่อโหลดโค้ดอันตรายลงในหน่วยความจำโดยไม่บันทึกไฟล์ลงดิสก์ |
| 4 | described | T1082 ? | ระบบได้ทำการเรียกคำสั่งเพื่อรวบรวมข้อมูลเกี่ยวกับระบบปฏิบัติการ ตัวประมวลผล และรายการซอฟต์แวร์ที่ติดตั้ง |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_023  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเว็บแอปพลิเคชันสาธารณะของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ส่ง HTTP request ที่มีค่า parameter ที่ผิดปกติไปยัง endpoint ของ payment processing module และสามารถบ่อนทำลายการตรวจสอบความปลอดภัยของเว็บแอปพลิเคชัน ต่อมาจากการวิเคราะห์ payload ที่ส่งเข้ามาพบว่าผู้โจมตีได้ใช้ประโยค syntax ที่ซ้อนกันเพื่อให้ระบบ template engine ประมวลผลคำสั่งที่ไม่ได้ตั้งใจ ซึ่งส่งผลให้ข้อมูลไฟล์ config และ database connection string ถูกเปิดเผย จากนั้นจากการติดตามการเชื่อมต่อเครือข่ายพบว่าผู้โจมตีได้นำเซิร์ฟเวอร์ proxy ตัวกลางมาใช้ในการสื่อสารกับระบบที่ถูกบุกรุก เพื่อปกปิดที่อยู่ IP ต้นทางและรักษาการเชื่อมต่อ command and control ให้คงอยู่ต่อเนื่อง

*EN:* On 22 February 2569, a private financial services company in Bangkok reported unauthorized access to its public-facing web application. Log analysis revealed that the attacker sent HTTP requests with anomalous parameter values to the payment processing module endpoint, successfully bypassing the application's security checks. Subsequent payload analysis showed the attacker used nested syntax constructs to force the template engine to process unintended commands, resulting in exposure of configuration files and database connection strings. Network traffic analysis then identified that the attacker routed communications through intermediate proxy servers to mask the source IP address and maintain persistent command and control connectivity to the compromised system.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1190 exploit public-facing application | ผู้โจมตีได้ส่ง HTTP request ที่มีค่า parameter ที่ผิดปกติไปยัง endpoint ของ payment processing module และสามารถบ่อนทำลายการตรวจสอบความปลอดภัยของเว็บแอปพลิเคชัน |
| 2 | described | T1221 template injection | ผู้โจมตีได้ใช้ประโยค syntax ที่ซ้อนกันเพื่อให้ระบบ template engine ประมวลผลคำสั่งที่ไม่ได้ตั้งใจ |
| 3 | described | T1090 ? | ผู้โจมตีได้นำเซิร์ฟเวอร์ proxy ตัวกลางมาใช้ในการสื่อสารกับระบบที่ถูกบุกรุก เพื่อปกปิดที่อยู่ IP ต้นทางและรักษาการเชื่อมต่อ command and control ให้คงอยู่ต่อเนื่อง |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_024  (source group: (previous run) )

> เมื่อวันที่ 12 กุมภาพันธ์ 2569 บริษัทบริการด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพ แจ้งความว่าระบบ CRM ของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีส่งไฟล์ Microsoft Word ที่มีการฝัง malicious macro ซึ่งเมื่อพนักงานเปิดไฟล์นั้นโปรแกรมอันตรายได้ทำงานบนเครื่องคอมพิวเตอร์เป้าหมาย ต่อมา ผู้โจมตีสร้างบัญชีผู้ใช้งานใหม่ชื่อ "support_admin" ด้วยสิทธิ์ Administrator เพื่อรักษาการเข้าถึงระบบในระยะยาว จากนั้นใช้ System Owner/User Discovery เพื่อระบุตัวตนของพนักงานฝ่ายบัญชีและผู้บริหารระดับสูง สุดท้าย ผู้โจมตีทำการ Screen Capture ของหน้าจออพยพ้อมรหัส PIN และข้อมูลการถ่ายโอนเงินแสดงบนจอภาพของผู้บริหาร

*EN:* On 12 February 2569, a financial services company in Bangkok reported unauthorized access to their CRM system. Log examination revealed that the attacker sent a Microsoft Word file with embedded malicious macros which, when opened by an employee, executed malicious code on the target computer. Subsequently, the attacker created a new user account named "support_admin" with Administrator privileges to maintain long-term system access. The attacker then used System Owner/User Discovery to identify the identities of accounting staff and senior management. Finally, the attacker performed Screen Capture of the executive's desktop displaying transaction codes, PINs, and fund transfer information on screen.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1203 ? | ผู้โจมตีส่งไฟล์ Microsoft Word ที่มีการฝัง malicious macro ซึ่งเมื่อพนักงานเปิดไฟล์นั้นโปรแกรมอันตรายได้ทำงานบนเครื่องคอมพิวเตอร์เป้าหมาย |
| 2 | described | T1078 valid accounts | ผู้โจมตีสร้างบัญชีผู้ใช้งานใหม่ชื่อ "support_admin" ด้วยสิทธิ์ Administrator เพื่อรักษาการเข้าถึงระบบในระยะยาว |
| 3 | named | T1033 system owner/user discovery | ใช้ System Owner/User Discovery เพื่อระบุตัวตนของพนักงานฝ่ายบัญชีและผู้บริหารระดับสูง |
| 4 | named | T1113 ? | ทำการ Screen Capture ของหน้าจออพยพ้อมรหัส PIN และข้อมูลการถ่ายโอนเงินแสดงบนจอภาพของผู้บริหาร |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_025  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานครแจ้งความว่าระบบเซิร์ฟเวอร์ Windows Server 2016 ของฝ่ายบัญชีถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Windows Management Instrumentation ผ่าน PowerShell script เพื่อรันคำสั่งระยะไกลและเรียกใช้ executable file ที่มีขนาดผิดปกติ ต่อมาจากการวิเคราะห์ Registry และ startup folder พบว่าผู้โจมตีได้ปรับแต่ง Boot or Logon Autostart Execution โดยสร้าง scheduled task ใหม่ และแก้ไข Run key ใน HKLM เพื่อให้ malware ทำงานอัตโนมัติทุกครั้งที่มีการรีบูตระบบ จากนั้นจากการตรวจสอบ network traffic พบว่ามีการเชื่อมต่อไปยัง HTTP endpoint ภายนอกเป็นประจำ โดยส่งข้อมูล credential และ system information ไปยังเซิร์ฟเวอร์ของผู้โจมตีผ่านช่องทาง HTTP request ที่ปกปิดอยู่ในการสื่อสารปกติ

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to its Windows Server 2016 system in the accounting department. Log analysis revealed that the attacker used Windows Management Instrumentation via PowerShell script to execute remote commands and run unusually-sized executable files. Subsequently, examination of Registry and startup folders showed the attacker had modified Boot or Logon Autostart Execution by creating a new scheduled task and editing the Run key in HKLM to ensure malware executed automatically on each system reboot. Network traffic analysis then revealed regular connections to an external HTTP endpoint, transmitting credentials and system information to the attacker's server through HTTP requests disguised within normal communications.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1047 windows management instrumentation | ผู้โจมตีได้ใช้ Windows Management Instrumentation ผ่าน PowerShell script เพื่อรันคำสั่งระยะไกล |
| 2 | named | T1547 boot or logon autostart execution | ผู้โจมตีได้ปรับแต่ง Boot or Logon Autostart Execution โดยสร้าง scheduled task ใหม่ และแก้ไข Run key ใน HKLM |
| 3 | described | T1102 ? | มีการเชื่อมต่อไปยัง HTTP endpoint ภายนอกเป็นประจำ โดยส่งข้อมูล credential และ system information ไปยังเซิร์ฟเวอร์ของผู้โจมตีผ่านช่องทาง HTTP request |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_026  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานคร ได้รับแจ้งเบาะแสจากฝ่ายเทคนิโลยีสารสนเทศว่าพบการเข้าถึงระบบ Active Directory ผ่านบัญชีผู้ใช้งานของพนักงานฝ่ายบัญชีที่ไม่ได้อยู่ในสำนักงานในขณะนั้น จากการตรวจสอบ log พบว่าบัญชีดังกล่าวถูกใช้เพื่อทำการเข้าถึงเครื่องแม่ข่ายและมีการ exploit ช่องโหว่ใน Windows kernel เพื่อเพิ่มสิทธิ์การเข้าถึงจาก user level ขึ้นเป็น administrator ต่อมาผู้โจมตีได้ทำการ Access Token Manipulation เพื่อสร้าง security context ที่มีสิทธิ์เทียมเท่ากับผู้ดูแลระบบ จากนั้นจึงได้ทำการดึง credentials ที่เก็บไว้ในเครื่องจักรเก็บรหัสผ่าน (password manager) ของผู้ใช้งานระดับผู้บริหารหลายคน ซึ่งรวมถึงรหัสผ่านสำหรับระบบธนาคารและบัญชี VPN ของบริษัท

*EN:* On 22 February 2569, a private financial services company in Bangkok received notification from the IT department that unauthorized access to the Active Directory system had been detected through a user account belonging to an accounting department employee who was not present in the office at that time. Log analysis revealed that the account was used to access the main server and exploit a vulnerability in the Windows kernel to escalate privileges from user level to administrator. Subsequently, the attacker performed Access Token Manipulation to create a security context with administrator-equivalent permissions. The attacker then extracted credentials stored in the password manager of several executive-level users, including passwords for the company's banking system and VPN accounts.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | บัญชีผู้ใช้งานของพนักงานฝ่ายบัญชีที่ไม่ได้อยู่ในสำนักงานในขณะนั้น |
| 2 | described | T1068 ? | exploit ช่องโหว่ใน Windows kernel เพื่อเพิ่มสิทธิ์การเข้าถึงจาก user level ขึ้นเป็น administrator |
| 3 | named | T1134 access token manipulation | ทำการ Access Token Manipulation เพื่อสร้าง security context ที่มีสิทธิ์เทียมเท่ากับผู้ดูแลระบบ |
| 4 | described | T1555 credentials from password stores | ทำการดึง credentials ที่เก็บไว้ในเครื่องจักรเก็บรหัสผ่าน (password manager) ของผู้ใช้งานระดับผู้บริหารหลายคน |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_027  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้รับแจ้งเบาะแสจากผู้เสียหายว่าระบบการทำงานของเซิร์ฟเวอร์หลักมีการเชื่อมต่อจากที่ไม่ทราบแหล่งที่มาอย่างต่อเนื่องผ่านช่องทางการเข้าถึงระยะไกล โดยผู้บุกรุกได้สร้างเสถียรภาพของการเชื่อมต่อดังกล่าวเพื่อรักษาการเข้าถึงในระยะยาว จากการตรวจสอบ log ของระบบ firewall พบว่าข้อมูลการเชื่อมต่อได้ถูกปิดบังด้วยการส่งสัญญาณเพื่อให้ระบบตรวจจับภัยคุณขาดการสังเกตการณ์ที่เพียงพอ ต่อมา ผู้โจมตีได้ทำการ Financial Theft โดยโอนเงินจากบัญชีลูกค้าจำนวน 47 บัญชี เป็นจำนวนเงินรวมประมาณ 8.3 ล้านบาท ไปยังบัญชีชั่วคราวที่ตั้งอยู่ในต่างประเทศ

*EN:* On 22 February 2569, a private financial services company in Bangkok received information from the victim that the company's primary server system was receiving continuous connections from unknown sources via remote access channels. The attacker had established stability of these connections to maintain long-term access. From examination of firewall logs, connection data was found to have been obscured through signaling that caused the detection system to lack sufficient monitoring capability. Subsequently, the attacker conducted Financial Theft by transferring funds from 47 customer accounts totaling approximately 8.3 million baht to temporary accounts located overseas.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1133 external remote services | ระบบการทำงานของเซิร์ฟเวอร์หลักมีการเชื่อมต่อจากที่ไม่ทราบแหล่งที่มาอย่างต่อเนื่องผ่านช่องทางการเข้าถึงระยะไกล โดยผู้บุกรุกได้สร้างเสถียรภาพของการเชื่อมต่อดังกล่าวเพื่อรักษาการเข้าถึงในระยะยาว |
| 2 | described | T1205 traffic signaling | ข้อมูลการเชื่อมต่อได้ถูกปิดบังด้วยการส่งสัญญาณเพื่อให้ระบบตรวจจับภัยคุณขาดการสังเกตการณ์ที่เพียงพอ |
| 3 | named | T1657 financial theft | ผู้โจมตีได้ทำการ Financial Theft โดยโอนเงินจากบัญชีลูกค้าจำนวน 47 บัญชี เป็นจำนวนเงินรวมประมาณ 8.3 ล้านบาท |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_028  (source group: (previous run) )

**AUTO-FLAGS: step 2: described cue names the technique (windows management instrumentation)**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทจัดการสินทรัพย์ดิจิทัลแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์หลักของตนถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Exploit Public-Facing Application ผ่านช่องโหว่ในเว็บแอปพลิเคชันหน้าสาธารณะเพื่อเข้าสู่ระบบ ต่อมาผู้โจมตีได้ดำเนินการสั่งงานผ่าน Windows Management Instrumentation เพื่อเรียกใช้สคริปต์ PowerShell ที่ซ่อนไว้ในหน่วยความจำ จากนั้นผู้โจมตีได้ขโมยข้อมูลประจำตัวของบัญชี Administrator ที่มีสิทธิ์สูงและใช้ Valid Accounts เพื่อเพิ่มพูนสิทธิการเข้าถึงระบบ สุดท้ายจากการตรวจสอบพบว่าผู้โจมตีได้ปลอมแปลงและซ่อนไฟล์ที่มีส่วนขยาย .exe ด้วยการเปลี่ยนแปลงแอตทริบิวต์และการเข้ารหัส จากนั้นดำเนินการ Ingress Tool Transfer โดยโหลดเครื่องมือ remote access ที่ไม่ได้รับอนุญาต และสุดท้ายทำการส่งข้อมูลไฟล์ฐานข้อมูลลูกค้าออกจากระบบผ่านช่องทางการติดต่อกับเซิร์ฟเวอร์ควบคุมระยะไกล

*EN:* On 22 February 2569, a digital asset management company in Bangkok reported unauthorized access to its primary server system. Log examination revealed that the attacker exploited a vulnerability in a public-facing web application to gain initial access. Subsequently, the attacker issued commands via Windows Management Instrumentation to execute hidden PowerShell scripts in memory. The attacker then stole Administrator account credentials and used Valid Accounts to escalate system privileges. Investigation further showed that the attacker obfuscated and concealed executable files by modifying file attributes and encryption. The attacker then performed Ingress Tool Transfer by downloading unauthorized remote access tools, and finally exfiltrated customer database files over the command-and-control channel.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1190 exploit public-facing application | ผู้โจมตีได้ใช้ Exploit Public-Facing Application ผ่านช่องโหว่ในเว็บแอปพลิเคชันหน้าสาธารณะ |
| 2 | described | T1047 windows management instrumentation | ผู้โจมตีได้ดำเนินการสั่งงานผ่าน Windows Management Instrumentation เพื่อเรียกใช้สคริปต์ PowerShell ที่ซ่อนไว้ในหน่วยความจำ |
| 3 | named | T1078 valid accounts | ผู้โจมตีได้ขโมยข้อมูลประจำตัวของบัญชี Administrator ที่มีสิทธิ์สูงและใช้ Valid Accounts เพื่อเพิ่มพูนสิทธิการเข้าถึงระบบ |
| 4 | described | T1027 ? | ผู้โจมตีได้ปลอมแปลงและซ่อนไฟล์ที่มีส่วนขยาย .exe ด้วยการเปลี่ยนแปลงแอตทริบิวต์และการเข้ารหัส |
| 5 | named | T1105 ? | ดำเนินการ Ingress Tool Transfer โดยโหลดเครื่องมือ remote access ที่ไม่ได้รับอนุญาต |
| 6 | described | T1041 ? | ทำการส่งข้อมูลไฟล์ฐานข้อมูลลูกค้าออกจากระบบผ่านช่องทางการติดต่อกับเซิร์ฟเวอร์ควบคุมระยะไกล |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_029  (source group: (previous run) )

**AUTO-FLAGS: step 3: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์ของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้บัญชีผู้ใช้งานที่ถูกต้องตามลำดับชั้นการเข้าถึงของเจ้าหน้าที่แอดมินระดับปานกลาง เพื่อเข้าสู่ระบบและรักษาการเชื่อมต่อ ต่อมาผู้โจมตีได้ทำการสร้าง BITS Jobs เพื่อดำเนินการดึงข้อมูลและซ่อนกิจกรรมจากระบบการตรวจสอบ จากนั้นใช้เครื่องมือ Ingress Tool Transfer เพื่อนำเข้าซอฟต์แวร์ที่เป็นอันตรายจากเซิร์ฟเวอร์ภายนอกไปยังเครื่องขั้ว internal network สุดท้ายผู้โจมตีได้ส่งข้อมูลที่ได้รับการสกัดออกมา Exfiltration Over C2 Channel ผ่านช่องทางการสื่อสารที่ซ่อนอยู่กับเซิร์ฟเวอร์ควบคุมภายนอก

*EN:* On 22 February 2569, a private financial company in Bangkok reported unauthorized access to its server systems. Digital forensic examination of logs revealed that the attacker used legitimate credentials aligned with mid-level administrator access privileges to establish and maintain system access. Subsequently, the attacker created BITS Jobs to execute data retrieval operations and evade audit system detection. The attacker then employed Ingress Tool Transfer to import malicious software from external servers into internal network endpoints. Finally, the attacker exfiltrated extracted data through Exfiltration Over C2 Channel via concealed communication channels to external command servers.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | ผู้โจมตีได้ใช้บัญชีผู้ใช้งานที่ถูกต้องตามลำดับชั้นการเข้าถึงของเจ้าหน้าที่แอดมินระดับปานกลาง เพื่อเข้าสู่ระบบและรักษาการเชื่อมต่อ |
| 2 | named | T1197 bits jobs | ผู้โจมตีได้ทำการสร้าง BITS Jobs เพื่อดำเนินการดึงข้อมูลและซ่อนกิจกรรมจากระบบการตรวจสอบ |
| 3 | named | T1105 ? | ใช้เครื่องมือ Ingress Tool Transfer เพื่อนำเข้าซอฟต์แวร์ที่เป็นอันตรายจากเซิร์ฟเวอร์ภายนอกไปยังเครื่องขั้น internal network |
| 4 | named | T1041 ? | ผู้โจมตีได้ส่งข้อมูลที่ได้รับการสกัดออกมา Exfiltration Over C2 Channel ผ่านช่องทางการสื่อสารที่ซ่อนอยู่กับเซิร์ฟเวอร์ควบคุมภายนอก |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_030  (source group: (previous run) )

**AUTO-FLAGS: step 3: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้รับแจ้งความจากพนักงานแผนกเทคโนโลยีสารสนเทศว่า ระบบ email client ของเซิร์ฟเวอร์ประจำสำนักงานหลักถูกสงสัยว่ามีการดำเนินการที่ผิดปกติ จากการตรวจสอบ log ระบบพบว่า ไฟล์ attachment ที่มีนามสกุล .exe ถูกเปิดขึ้นมาในระบบของผู้ใช้ระดับพนักงาน และทำให้เกิดการรันคำสั่งที่ไม่ได้รับการอนุญาต ต่อมา ผู้โจมตีได้ทำการ Valid Accounts โดยการยักยอกข้อมูลชื่อผู้ใช้และรหัสผ่านของพนักงานระดับหัวหน้าแผนกจากฐานข้อมูล และใช้บัญชีดังกล่าวเข้าสู่ระบบ VPN เพื่อเข้าถึงเครือข่ายภายในบริษัท จากนั้น จากการตรวจสอบ network traffic พบว่า มีการสื่อสารระหว่างเซิร์ฟเวอร์ของบริษัทและเซิร์ฟเวอร์ภายนอกอย่างต่อเนื่อง โดยข้อมูลการเข้าสู่ระบบและรหัสผ่านของบัญชีผู้ใช้อื่นๆ ถูกสกัดและส่งออกไปในระหว่างการสื่อสารนี้ ซึ่งบ่งชี้ว่ามีการติดตั้ง proxy หรืออุปกรณ์สอดแนมอื่นๆ ไว้ในเส้นทางการสื่อสารของระบบเครือข่าย

*EN:* On 22 February 2569, a private financial company in Bangkok received a report from an IT department employee that the email client system on the main office server exhibited suspicious activity. Upon examination of system logs, an executable file (.exe) was found to have been opened on an employee-level user's system, resulting in unauthorized command execution. Subsequently, the attacker obtained Valid Accounts by extracting the username and password of a department head from the database and used that account to access the company's VPN system and internal network. Further investigation of network traffic revealed continuous communication between the company's server and external servers, during which login credentials and passwords of other user accounts were intercepted and exfiltrated. This indicated the installation of a proxy or packet-sniffing device positioned within the network communication pathway.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1203 ? | ไฟล์ attachment ที่มีนามสกุล .exe ถูกเปิดขึ้นมาในระบบของผู้ใช้ระดับพนักงาน และทำให้เกิดการรันคำสั่งที่ไม่ได้รับการอนุญาต |
| 2 | named | T1078 valid accounts | ผู้โจมตีได้ทำการ Valid Accounts โดยการยักยอกข้อมูลชื่อผู้ใช้และรหัสผ่านของพนักงานระดับหัวหน้าแผนก |
| 3 | described | T1557 ? | มีการสอดแนมข้อมูลการเข้าสู่ระบบและรหัสผ่านของบัญชีผู้ใช้อื่นๆ ถูกสกัดและส่งออกไปในระหว่างการสื่อสารนี้ ซึ่งบ่งชี้ว่ามีการติดตั้ง proxy หรืออุปกรณ์สอดแนมอื่นๆ ไว้ในเส้นทางการสื่อสารของระบบเครือข่าย |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_031  (source group: (previous run) )

**AUTO-FLAGS: step 5: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานคร ได้รับแจ้งเบาะแสจากฝ่ายเทคโนโลยีสารสนเทศว่าระบบ workstation สำนักงานถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log authentication พบว่าผู้โจมตีใช้ Valid Accounts ของพนักงานระดับปฏิบัติการเข้าสู่ระบบหลังเวลา 23:00 น. ต่อมา จากการวิเคราะห์ event log ของ Windows พบร่องรอยการใช้ Windows Management Instrumentation ผ่านคำสั่ง wmic เพื่อดำเนินการควบคุมระบบจากระยะไกล จากนั้น ผู้โจมตีทำการแก้ไขค่าต่าง ๆ ในส่วน Registry เพื่อปิดการใช้งาน Windows Defender และ security event logging ตามที่พบจากการเปรียบเทียบ registry hive ที่สำรองไว้ สุดท้าย ผู้โจมตีทำการค้นหาและอ่านค่าต่าง ๆ จากส่วน Registry เพื่อเก็บข้อมูลเกี่ยวกับการตั้งค่าระบบและข้อมูลประจำตัวที่เก็บไว้ในเครื่อง จากนั้น ผู้โจมตีทำการ Ingress Tool Transfer โดยถ่ายโอน ransomware executable ขนาด 4.2 MB ผ่านช่อง SMB share ที่ยังไม่ได้ป้องกัน สุดท้าย ระบบได้รับการเข้ารหัส Data Encrypted for Impact โดยไฟล์ข้อมูลทั้งหมดถูกเข้ารหัสด้วยอัลกอริทึม AES-256 และปรากฏข้อความเรียกค่าไถ่บนหน้าจอ

*EN:* On 22 February 2569, a private financial company in Bangkok received notice from its IT department that an office workstation had been accessed without authorization. Log analysis revealed that the attacker used Valid Accounts belonging to an operational-level employee to log in after 23:00. Subsequently, Windows event log analysis showed traces of Windows Management Instrumentation being used via wmic commands to perform remote system control. The attacker then modified Registry values to disable Windows Defender and security event logging, as confirmed by comparing backed-up registry hives. The attacker then queried and read Registry values to gather information about system configuration and credentials stored on the machine. The attacker then performed Ingress Tool Transfer by moving a 4.2 MB ransomware executable across an unprotected SMB share. Finally, the system underwent Data Encrypted for Impact, with all data files encrypted using AES-256 algorithm and a ransom message displayed on screen.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 valid accounts | ผู้โจมตีใช้ Valid Accounts ของพนักงานระดับปฏิบัติการเข้าสู่ระบบ |
| 2 | named | T1047 windows management instrumentation | พบร่องรอยการใช้ Windows Management Instrumentation ผ่านคำสั่ง wmic |
| 3 | described | T1112 modify registry | ผู้โจมตีทำการแก้ไขค่าต่าง ๆ ในส่วน Registry เพื่อปิดการใช้งาน Windows Defender และ security event logging |
| 4 | described | T1012 query registry | ผู้โจมตีทำการค้นหาและอ่านค่าต่าง ๆ จากส่วน Registry เพื่อเก็บข้อมูลเกี่ยวกับการตั้งค่าระบบและข้อมูลประจำตัว |
| 5 | named | T1105 ? | ผู้โจมตีทำการ Ingress Tool Transfer โดยถ่ายโอน ransomware executable ผ่านช่อง SMB share |
| 6 | named | T1486 data encrypted for impact | ระบบได้รับการเข้ารหัส Data Encrypted for Impact โดยไฟล์ข้อมูลทั้งหมดถูกเข้ารหัสด้วยอัลกอริทึม AES-256 |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_032  (source group: (previous run) )

**AUTO-FLAGS: step 5: cue not found verbatim in narrative**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบ Windows Server ของฝ่ายบัญชีถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีใช้บัญชี Active Directory ของพนักงานอดีตที่ยังไม่ถูกปิดการใช้งาน เพื่อเข้าสู่เครื่องสถานีงาน ต่อมาผู้โจมตีได้ส่ง malicious PDF attachment ผ่าน email ที่มี embedded exploit code สำหรับ Adobe Reader ซึ่งเมื่อผู้ใช้เปิดไฟล์ดังกล่าว ระบบได้ดาวน์โหลด shellcode และรันเป็น process ลูกของ AdobeReader จากนั้นผู้โจมตีได้ใช้ UAC bypass technique โดยเรียก eventvwr.exe ซึ่ง auto-elevate โดยไม่ขอ prompt ผลการตรวจสอบ memory dump พบการใช้ Network sniffing ผ่านเครื่องมือ Wireshark เพื่อจับแพ็กเก็ต SMTP และ IMAP traffic ที่บรรจุข้อมูลรหัสผ่าน สุดท้ายผู้โจมตีได้แก้ไขไฟล์ startup script ในโฟลเดอร์ ProgramData\Microsoft\Windows\Start Menu\Programs\Startup เพื่อให้ reverse shell ทำการเชื่อมต่อกลับทุกครั้งที่มีการ logon ใหม่

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to a Windows Server in the accounting department. Log examination revealed the attacker used a disabled former employee Active Directory account to access a workstation. Subsequently, the attacker sent a malicious PDF attachment via email containing embedded exploit code for Adobe Reader; when the user opened the file, shellcode was downloaded and executed as a child process of AdobeReader. The attacker then employed a UAC bypass technique by invoking eventvwr.exe, which auto-elevates without prompting. Memory dump analysis revealed the use of Network sniffing via Wireshark to capture SMTP and IMAP traffic containing password data. Finally, the attacker modified startup scripts in the ProgramData\Microsoft\Windows\Start Menu\Programs\Startup folder to ensure a reverse shell reconnected on each new logon.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | ผู้โจมตีใช้บัญชี Active Directory ของพนักงานอดีตที่ยังไม่ถูกปิดการใช้งาน เพื่อเข้าสู่เครื่องสถานีงาน |
| 2 | described | T1203 ? | ผู้โจมตีได้ส่ง malicious PDF attachment ผ่าน email ที่มี embedded exploit code สำหรับ Adobe Reader ซึ่งเมื่อผู้ใช้เปิดไฟล์ดังกล่าว ระบบได้ดาวน์โหลด shellcode และรันเป็น process ลูกของ AdobeReader |
| 3 | described | T1548 ? | ผู้โจมตีได้ใช้ UAC bypass technique โดยเรียก eventvwr.exe ซึ่ง auto-elevate โดยไม่ขอ prompt |
| 4 | named | T1068 ? | UAC bypass technique |
| 5 | named | T1040 network sniffing | ผู้โจมตีได้แสดงการใช้ Network sniffing ผ่านเครื่องมือ Wireshark เพื่อจับแพ็กเก็ต SMTP และ IMAP traffic ที่บรรจุข้อมูลรหัสผ่าน |
| 6 | described | T1037 ? | ผู้โจมตีได้แก้ไขไฟล์ startup script ในโฟลเดอร์ ProgramData\Microsoft\Windows\Start Menu\Programs\Startup เพื่อให้ reverse shell ทำการเชื่อมต่อกลับทุกครั้งที่มีการ logon ใหม่ |

- [ ] ผ่าน / แก้แล้ว

## inc_auto_033  (source group: (previous run) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการคลาวด์เอกชนแห่งหนึ่งในจังหวัดกรุงเทพมหานคร ได้รับแจ้งเบาะแสจากผู้ดูแลระบบว่าพบกิจกรรมที่ผิดปกติในสภาพแวดล้อม container orchestration จากการตรวจสอบ log พบว่าผู้โจมตีได้ดำเนินการคำสั่งบริหารจัดการ container ผ่านทาง API endpoint โดยใช้ credentials ที่ได้มาจากแหล่งอื่น ต่อมาจากการวิเคราะห์เพิ่มเติมพบว่าผู้โจมตีได้สร้าง external remote services เพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่อง จากนั้นผู้โจมตีได้ทำการ escape to host โดยใช้ช่องโหว่ใน container runtime เพื่อเข้าถึงระบบปฏิบัติการโฮสต์โดยตรง สุดท้ายจากการตรวจสอบไฟล์ระบบพบว่าชื่อผู้ใช้และชื่อกระบวนการได้ถูกปลอมแปลงให้ดูเหมือนเป็นบริการระบบปกติ เพื่อหลีกเลี่ยงการตรวจสอบของผู้ดูแลระบบ จากนั้นผู้โจมตีได้ทำการถ่ายโอนเครื่องมือการโจมตีเพิ่มเติมจากเซิร์ฟเวอร์ภายนอกไปยังเครื่องอื่น ๆ ในเครือข่ายภายใน สุดท้ายข้อมูลที่ละเอียดอ่อนจำนวนมากได้ถูกส่งออกไปจากเครือข่ายโดยใช้ DNS tunneling protocol เป็นช่องทางการสื่อสารแทนการใช้ HTTP ปกติ

*EN:* On 22 February 2569, a private cloud services company in Bangkok received notice from a system administrator of unusual activity detected in the container orchestration environment. Upon examination of logs, it was found that the attacker had executed administrative commands on containers via the API endpoint using credentials obtained from another source. Further analysis revealed that the attacker had established external remote services to maintain persistent access to the system. Subsequently, the attacker performed an escape to host operation by exploiting a vulnerability in the container runtime to gain direct access to the underlying host operating system. Examination of system files then showed that usernames and process names had been masqueraded to appear as normal system services in order to evade administrator detection. The attacker then transferred additional attack tools from an external server to other machines on the internal network. Finally, a large volume of sensitive data was exfiltrated from the network using DNS tunneling protocol as the communication channel instead of standard HTTP.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1609 container administration command | ผู้โจมตีได้ดำเนินการคำสั่งบริหารจัดการ container ผ่านทาง API endpoint โดยใช้ credentials ที่ได้มาจากแหล่งอื่น |
| 2 | named | T1133 external remote services | ผู้โจมตีได้สร้าง external remote services เพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่อง |
| 3 | named | T1611 escape to host | ผู้โจมตีได้ทำการ escape to host โดยใช้ช่องโหว่ใน container runtime เพื่อเข้าถึงระบบปฏิบัติการโฮสต์โดยตรง |
| 4 | described | T1036 ? | ชื่อผู้ใช้และชื่อกระบวนการได้ถูกปลอมแปลงให้ดูเหมือนเป็นบริการระบบปกติ |
| 5 | described | T1105 ? | ผู้โจมตีได้ทำการถ่ายโอนเครื่องมือการโจมตีเพิ่มเติมจากเซิร์ฟเวอร์ภายนอกไปยังเครื่องอื่น ๆ ในเครือข่ายภายใน |
| 6 | named | T1048 ? | ข้อมูลที่ละเอียดอ่อนจำนวนมากได้ถูกส่งออกไปจากเครือข่ายโดยใช้ DNS tunneling protocol |

- [ ] ผ่าน / แก้แล้ว
