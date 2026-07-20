# Incident Draft Review Sheet

ตรวจแต่ละข้อ: (1) สำนวนเหมือนสำนวนคดีจริงไหม (2) cue ตรงกับ technique จริงไหม
(3) step แบบ described ไม่เผลอบอกชื่อเทคนิค — แก้ไขในไฟล์ incident_draft.json
แล้วลบข้อที่ใช้ไม่ได้ทิ้ง

## inc_camp_001  (source: Leviathan Australian Intrusions (C0049, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพ แจ้งความว่าระบบ email server ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีใช้ Valid Accounts ของพนักงานแผนกการเงินเพื่อเข้าสู่ระบบ ต่อมาผู้โจมตีทำการ Multi-Factor Authentication Interception โดยสกัดข้อความ OTP ที่ส่งไปยังโทรศัพท์มือถือของเจ้าของบัญชี เพื่อให้สามารถเข้าใช้งานระบบได้อย่างสมบูรณ์ จากนั้นผู้โจมตีทำการ Remote System Discovery ค้นหาเครื่องคอมพิวเตอร์อื่น ๆ ในเครือข่ายภายในบริษัท ด้วยการส่ง ping และ port scanning สำหรับจากการตรวจสอบไฟล์ log ของเซิร์ฟเวอร์พบร่องรอยของการติดตั้ง keylogger บนเครื่องที่ถูกโจมตี ซึ่งบันทึกการกดแป้นพิมพ์ของผู้ใช้งานอย่างต่อเนื่อง สุดท้ายข้อมูลที่ได้รวบรวมไว้ถูกส่งออกไปยังเซิร์ฟเวอร์ภายนอกผ่านช่องทาง command and control ที่ซ่อนอยู่ในการสื่อสารที่ดูเหมือนปกติ

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to its email server. Log analysis revealed that the attacker used Valid Accounts belonging to an employee in the finance department to gain system access. Subsequently, the attacker intercepted Multi-Factor Authentication by intercepting OTP messages sent to the account owner's mobile phone to achieve full system access. The attacker then performed Remote System Discovery to identify other computers within the company network using ping and port scanning techniques. Examination of server logs revealed evidence of a keylogger installed on the compromised machine, which continuously recorded user keystrokes. Finally, the collected data was exfiltrated to an external server through a command and control channel disguised within normal-appearing communications.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1078 valid accounts | ผู้โจมตีใช้ Valid Accounts ของพนักงานแผนกการเงิน |
| 2 | named | T1111 multi-factor authentication interception | ผู้โจมตีทำการ Multi-Factor Authentication Interception โดยสกัดข้อความ OTP ที่ส่งไปยังโทรศัพท์มือถือของเจ้าของบัญชี |
| 3 | named | T1018 remote system discovery | ผู้โจมตีทำการ Remote System Discovery ค้นหาเครื่องคอมพิวเตอร์อื่น ๆ ในเครือข่ายภายในบริษัท ด้วยการส่ง ping และ port scanning |
| 4 | described | T1056 ? | การติดตั้ง keylogger บนเครื่องที่ถูกโจมตี ซึ่งบันทึกการกดแป้นพิมพ์ของผู้ใช้งานอย่างต่อเนื่อง |
| 5 | described | T1041 ? | ข้อมูลที่ได้รวบรวมไว้ถูกส่งออกไปยังเซิร์ฟเวอร์ภายนอกผ่านช่องทาง command and control ที่ซ่อนอยู่ในการสื่อสารที่ดูเหมือนปกติ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_002  (source: C0015 (C0015, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์หลักของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ของระบบ firewall พบว่าผู้โจมตีได้ใช้ Remote System Discovery เพื่อค้นหาอุปกรณ์เครือข่ายและเซิร์ฟเวอร์ที่เชื่อมต่อในโครงสร้างพื้นฐาน ต่อมา จากบันทึก proxy server พบร่องรอยการดาวน์โหลดเครื่องมือจากเซิร์ฟเวอร์ภายนอก โดยมีการส่งไฟล์ executable ขนาดเล็กหลายไฟล์เข้ามาในระบบเป้าหมายผ่านช่องทาง HTTP ในช่วงเวลาต่างๆ จากนั้น จากการวิเคราะห์ traffic ของระบบพบว่ามีการเชื่อมต่อ outbound ไปยังเซิร์ฟเวอร์ภายนอกด้วยจำนวนข้อมูลที่ถูกควบคุมและแบ่งเป็นส่วนเล็กๆ เพื่อหลีกเลี่ยงการตรวจจับจากระบบ IDS สุดท้าย ทีมสอบสวนจึงอุ่นเครื่องเก็บข้อมูลฉุกเฉินและรวบรวมหลักฐานดิจิทัลสำหรับการสอบสวนเพิ่มเติม

*EN:* On 22 February 2569, an information technology private company in Bangkok reported unauthorized access to their main server system. From examination of firewall logs, it was found that the attacker used Remote System Discovery to identify networked devices and servers connected to the infrastructure. Subsequently, proxy server records revealed traces of tool downloads from external servers, with multiple small executable files transferred into the target system via HTTP channels at various times. Then, from analysis of system traffic, outbound connections to external servers were observed with data quantities controlled and divided into small portions to evade IDS detection. Finally, the investigation team activated emergency data collection procedures and gathered digital evidence for further investigation.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1018 remote system discovery | ผู้โจมตีได้ใช้ Remote System Discovery เพื่อค้นหาอุปกรณ์เครือข่ายและเซิร์ฟเวอร์ที่เชื่อมต่อในโครงสร้างพื้นฐาน |
| 2 | described | T1105 ? | มีการส่งไฟล์ executable ขนาดเล็กหลายไฟล์เข้ามาในระบบเป้าหมายผ่านช่องทาง HTTP ในช่วงเวลาต่างๆ |
| 3 | described | T1030 data transfer size limits | มีการเชื่อมต่อ outbound ไปยังเซิร์ฟเวอร์ภายนอกด้วยจำนวนข้อมูลที่ถูกควบคุมและแบ่งเป็นส่วนเล็กๆ เพื่อหลีกเลี่ยงการตรวจจับจากระบบ IDS |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_003  (source: 2016 Ukraine Electric Power Attack (C0025, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนจัดการสินค้าแห่งหนึ่งในจังหวัดสมุทรปราการได้รับแจ้งเบาะแสจากแผนกเทคโนโลยีสารสนเทศว่าระบบเซิร์ฟเวอร์หลักมีกิจกรรมที่ผิดปกติ จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Windows Management Instrumentation เพื่อรันคำสั่งเบื้องต้นและติดตั้งเครื่องมือเพิ่มเติมบนระบบ ต่อมาพบการสร้างบัญชีผู้ใช้งานใหม่ที่ไม่อยู่ในรายชื่อพนักงานของบริษัท พร้อมกับการแก้ไขสิทธิ์การเข้าถึงให้บัญชีนี้มีสถานะผู้ดูแลระบบแบบซ่อนเร้น จากนั้นระบบตรวจจับการพยายาม Brute Force ต่อบัญชีผู้ใช้งานหลายรายด้วยรหัสผ่านที่เปลี่ยนแปลงอย่างรวดเร็ว และสุดท้ายพบการถ่ายโอนไฟล์เครื่องมือโจมตีขนาดใหญ่ผ่านช่องทางเครือข่ายไปยังอุปกรณ์อื่นๆ ภายในเครือข่ายภายในของบริษัท

*EN:* On 22 February 2569, a private goods management company in Samut Prakan Province received an alert from the Information Technology Department that the main server system showed unusual activity. Upon examination of logs, it was found that the attacker used Windows Management Instrumentation to execute initial commands and deploy additional tools on the system. Subsequently, a new user account was created that did not appear on the company's employee roster, accompanied by modification of access rights to grant this account hidden administrator privileges. The system then detected Brute Force attempts against multiple user accounts using rapidly changing passwords, and finally file transfers of attack tools of considerable size were observed across network channels to other devices within the company's internal network.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1047 windows management instrumentation | ผู้โจมตีได้ใช้ Windows Management Instrumentation เพื่อรันคำสั่งเบื้องต้นและติดตั้งเครื่องมือเพิ่มเติมบนระบบ |
| 2 | described | T1136 create account | พบการสร้างบัญชีผู้ใช้งานใหม่ที่ไม่อยู่ในรายชื่อพนักงานของบริษัท |
| 3 | named | T1098 account manipulation | การแก้ไขสิทธิ์การเข้าถึงให้บัญชีนี้มีสถานะผู้ดูแลระบบแบบซ่อนเร้น |
| 4 | named | T1110 brute force | ระบบตรวจจับการพยายาม Brute Force ต่อบัญชีผู้ใช้งานหลายรายด้วยรหัสผ่านที่เปลี่ยนแปลงอย่างรวดเร็ว |
| 5 | described | T1570 lateral tool transfer | พบการถ่ายโอนไฟล์เครื่องมือโจมตีขนาดใหญ่ผ่านช่องทางเครือข่ายไปยังอุปกรณ์อื่นๆ ภายในเครือข่ายภายในของบริษัท |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_004  (source: 3CX Supply Chain Attack (C0057, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนแห่งหนึ่งในจังหวัดสมุทรปราการที่ประกอบธุรกิจด้านการขนส่งและโลจิสติกส์ได้แจ้งความว่าระบบคอมพิวเตอร์ของพนักงานฝ่ายขาย ถูกทำให้เสียหายหลังจากเข้าชมเว็บไซต์ที่มีเนื้อหาเกี่ยวกับการจัดการลูกค้า โดยเว็บไซต์ดังกล่าวมี drive-by compromise ฝังอยู่ในโค้ด JavaScript ซึ่งทำให้เกิดการดาวน์โหลดและรันไฟล์ที่มีอันตรายโดยอัตโนมัติ จากการตรวจสอบ log พบว่าไฟล์ที่ทำให้เสียหายนั้นได้ใช้ Inter-Process Communication เพื่อเชื่อมต่อกับ process ของระบบและส่งคำสั่งควบคุมเพิ่มเติม ต่อมาผู้โจมตีทำการสร้าง Valid Accounts ขึ้นมาใหม่ในระบบ Active Directory โดยใช้ชื่อผู้ใช้และรหัสผ่านที่มีลักษณะคล้ายกับบัญชีพนักงานจริง เพื่อรักษาการเข้าถึงระบบอย่างต่อเนื่อง จากนั้นผู้โจมตีได้ทำการ Process Injection โดยแทรกโค้ดร้ายลงในกระบวนการของระบบปฏิบัติการที่มีสิทธิสูง เพื่อให้ได้รับสิทธิในการควบคุมระบบได้อย่างเต็มที่ สุดท้ายจากการวิเคราะห์ evidence พบร่องรอยการเข้าถึงข้อมูลจำนวนมากจากเบราว์เซอร์ รวมถึงการอ่านไฟล์ cookies, cached data และ history ของการเข้าชมเว็บไซต์ต่างๆ ที่เก็บไว้ในเบราว์เซอร์

*EN:* On 22 February 2569, a private logistics and transportation company in Samut Prakan Province reported that an employee's computer in the sales department was compromised after visiting a website containing customer management content, which had a drive-by compromise embedded in JavaScript code that automatically downloaded and executed malicious files. Log examination revealed that the malicious file used Inter-Process Communication to connect with system processes and send additional control commands. Subsequently, the attacker created Valid Accounts in the Active Directory system using usernames and passwords resembling those of actual employees to maintain persistent system access. The attacker then performed Process Injection by injecting malicious code into high-privilege operating system processes to gain full system control. Finally, evidence analysis revealed traces of extensive data access from the browser, including the reading of cookies, cached data, and browsing history of various websites stored in the browser.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1189 ? | เว็บไซต์ดังกล่าวมี drive-by compromise ฝังอยู่ในโค้ด JavaScript ซึ่งทำให้เกิดการดาวน์โหลดและรันไฟล์ที่มีอันตรายโดยอัตโนมัติ |
| 2 | named | T1559 inter-process communication | ไฟล์ที่ทำให้เสียหายนั้นได้ใช้ Inter-Process Communication เพื่อเชื่อมต่อกับ process ของระบบและส่งคำสั่งควบคุมเพิ่มเติม |
| 3 | named | T1078 valid accounts | ผู้โจมตีทำการสร้าง Valid Accounts ขึ้นมาใหม่ในระบบ Active Directory โดยใช้ชื่อผู้ใช้และรหัสผ่านที่มีลักษณะคล้ายกับบัญชีพนักงานจริง |
| 4 | named | T1055 ? | ผู้โจมตีได้ทำการ Process Injection โดยแทรกโค้ดร้ายลงในกระบวนการของระบบปฏิบัติการที่มีสิทธิสูง |
| 5 | described | T1217 browser information discovery | การเข้าถึงข้อมูลจำนวนมากจากเบราว์เซอร์ รวมถึงการอ่านไฟล์ cookies, cached data และ history ของการเข้าชมเว็บไซต์ต่างๆ ที่เก็บไว้ในเบราว์เซอร์ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_005  (source: Operation CuckooBees (C0012, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบเซิร์ฟเวอร์ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log และ firewall records พบว่าผู้โจมตีได้สร้างการเชื่อมต่อ SSH ผ่านบัญชีผู้ดูแลระบบที่มีอยู่แล้ว และยังคงรักษาการเข้าถึงจากระยะไกลผ่านการตั้งค่า reverse shell ไว้เพื่อการกลับมาในภายหลัง ต่อมาจากการตรวจสอบประวัติการทำงานของระบบพบว่าผู้โจมตีได้ดำเนินการ Network Share Discovery เพื่อค้นหาเครื่องคอมพิวเตอร์อื่นและไดรฟ์ที่แชร์ข้อมูลบนเครือข่ายภายในองค์กร จากนั้นผู้โจมตีได้ทำการรวบรวมข้อมูลจากเครื่องเซิร์ฟเวอร์ท้องถิ่น ประกอบด้วยไฟล์ฐานข้อมูลลูกค้า ข้อมูลการจัดส่งสินค้า และไฟล์การตั้งค่าระบบ โดยคัดลอกข้อมูลเหล่านี้ไปยังตำแหน่งชั่วคราวบนเซิร์ฟเวอร์ก่อนการส่งออก

*EN:* On 22 February 2569, a logistics service company in Samut Prakan Province reported that its server system had been accessed without authorization. From examination of logs and firewall records, it was found that the attacker established an SSH connection using an existing administrator account and maintained remote access through reverse shell configuration for future return. Subsequently, from inspection of system activity history, the attacker conducted Network Share Discovery to identify other computers and shared drives containing data on the internal network. The attacker then collected data from the local server, including customer database files, shipment information, and system configuration files, by copying these data to a temporary location on the server before exfiltration.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1133 external remote services | ได้สร้างการเชื่อมต่อ SSH ผ่านบัญชีผู้ดูแลระบบที่มีอยู่แล้ว และยังคงรักษาการเข้าถึงจากระยะไกลผ่านการตั้งค่า reverse shell ไว้เพื่อการกลับมาในภายหลัง |
| 2 | named | T1135 network share discovery | ผู้โจมตีได้ดำเนินการ Network Share Discovery เพื่อค้นหาเครื่องคอมพิวเตอร์อื่นและไดรฟ์ที่แชร์ข้อมูลบนเครือข่ายภายในองค์กร |
| 3 | described | T1005 ? | ผู้โจมตีได้ทำการรวบรวมข้อมูลจากเครื่องเซิร์ฟเวอร์ท้องถิ่น ประกอบด้วยไฟล์ฐานข้อมูลลูกค้า ข้อมูลการจัดส่งสินค้า และไฟล์การตั้งค่าระบบ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_006  (source: 2015 Ukraine Electric Power Attack (C0028, campaign) )

> เมื่อวันที่ 12 กุมภาพันธ์ 2569 บริษัทบริหารจัดการข้อมูลอุตสาหกรรมแห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบ Windows Server ของแผนกบัญชีถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ memory dump และ process log พบว่าผู้โจมตีทำการ Process Injection เข้าไปยังโปรแกรม svchost.exe เพื่อให้ได้สิทธิ์สูงขึ้น ต่อมาจากการวิเคราะห์ packet capture ที่บันทึกไว้ในช่วงเวลาผิดปกติ พบการส่งข้อมูล HTTP request ที่ไม่ปกติไปยังอุปกรณ์บนเครือข่ายภายในซึ่งดูเหมือนเป็นการสอดแนมการรับส่งข้อมูล เพื่อดักจับข้อมูลการเข้าสู่ระบบ จากนั้นจากการตรวจสอบ firewall log และ DNS query history พบว่ามีการค้นหาและเชื่อมต่อไปยังอุปกรณ์อื่น ๆ ในเครือข่ายเพื่อแมปโครงสร้างและตำแหน่งของระบบคอมพิวเตอร์ต่าง ๆ ทั้งหมด

*EN:* On 12 February 2569, a data management company in Samut Prakan Province reported unauthorized access to a Windows Server in the accounting department. Upon examination of memory dumps and process logs, it was found that the attacker performed Process Injection into the svchost.exe process to obtain elevated privileges. Subsequently, analysis of packet captures recorded during the anomalous period revealed unusual HTTP requests being sent to devices on the internal network, appearing to be network traffic interception to harvest login credentials. Further examination of firewall logs and DNS query history showed connections and queries to other devices on the network in order to map the structure and location of all computing systems.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1055 ? | ผู้โจมตีทำการ Process Injection เข้าไปยังโปรแกรม svchost.exe เพื่อให้ได้สิทธิ์สูงขึ้น |
| 2 | described | T1040 network sniffing | จากการวิเคราะห์ packet capture ที่บันทึกไว้ในช่วงเวลาผิดปกติ พบการส่งข้อมูล HTTP request ที่ไม่ปกติไปยังอุปกรณ์บนเครือข่ายภายในซึ่งดูเหมือนเป็นการสอดแนมการรับส่งข้อมูล เพื่อดักจับข้อมูลการเข้าสู่ระบบ |
| 3 | described | T1018 remote system discovery | จากการตรวจสอบ firewall log และ DNS query history พบว่ามีการค้นหาและเชื่อมต่อไปยังอุปกรณ์อื่น ๆ ในเครือข่ายเพื่อแมปโครงสร้างและตำแหน่งของระบบคอมพิวเตอร์ต่าง ๆ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_007  (source: CostaRicto (C0004, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาตผ่านช่องทางการเชื่อมต่อระยะไกลที่ยังคงเปิดอยู่ จากการตรวจสอบ log พบว่าผู้โจมตีได้ทำการสแกนหาบริการเครือข่ายที่ทำงานอยู่บนอุปกรณ์ต่างๆ ภายในโครงข่ายภายในของบริษัท เพื่อระบุจุดอ่อนและช่องทางการเข้าถึงเพิ่มเติม ต่อมา ผู้โจมตีได้ใช้ Protocol tunneling เพื่อสร้างช่องทางการสื่อสารแบบเข้ารหัสผ่านพอร์ต HTTPS ทำให้สามารถส่งคำสั่งและควบคุมระบบจากระยะไกลได้อย่างต่อเนื่อง จากนั้นผู้โจมตียังคงรักษาการเข้าถึงระบบไว้เป็นระยะเวลานาน เพื่อดำเนินการโจมตีในระยะต่อไป

*EN:* On 22 February 2569, a financial services company in Bangkok reported that its primary server was accessed without authorization through an open remote connection channel. Upon examination of logs, investigators found that the attacker performed network service discovery scans to identify running services on various devices within the company's internal network to locate vulnerabilities and additional access points. Subsequently, the attacker used protocol tunneling to establish an encrypted communication channel over HTTPS port, enabling remote command execution and system control. The attacker then maintained persistent access to the system for an extended period to conduct follow-up attack operations.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1133 external remote services | ระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาตผ่านช่องทางการเชื่อมต่อระยะไกลที่ยังคงเปิดอยู่ |
| 2 | described | T1046 network service discovery | ผู้โจมตีได้ทำการสแกนหาบริการเครือข่ายที่ทำงานอยู่บนอุปกรณ์ต่างๆ ภายในโครงข่ายภายในของบริษัท |
| 3 | named | T1572 protocol tunneling | ผู้โจมตีได้ใช้ Protocol tunneling เพื่อสร้างช่องทางการสื่อสารแบบเข้ารหัสผ่านพอร์ต HTTPS |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_008  (source: Operation Spalax (C0005, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพมหานครแจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ส่งคำสั่งผ่านทาง PowerShell เพื่อดาวน์โหลดไฟล์สคริปต์ที่ซ่อนไว้ในโฟลเดอร์ระบบ ต่อมาจากการวิเคราะห์พยานหลักฐานดิจิทัลพบว่ามีการตรวจสอบสภาพแวดล้อมของเครื่องเพื่อตรวจหาการทำงานภายในสภาพแวดล้อมเสมือน โดยตรวจสอบการมีอยู่ของเครื่องมือ virtualization ทั่วไป จากนั้นผู้โจมตีได้ใช้ Dynamic Resolution เพื่อแปลงชื่อโดเมนที่ซ่อนไว้ให้เป็นที่อยู่ IP ที่เปลี่ยนแปลงได้ เพื่อสื่อสารกับเซิร์ฟเวอร์ Command and Control ที่อยู่ในต่างประเทศ

*EN:* On 22 February 2569, a private financial services company in Bangkok reported unauthorized access to its primary server. From log analysis, investigators found that the attacker had issued commands via PowerShell to download a script file hidden in a system folder. Subsequent digital forensic examination revealed that the system environment was probed to detect execution within virtual environments by checking for common virtualization tools. The attacker then used Dynamic Resolution to translate obfuscated domain names into dynamically changing IP addresses in order to communicate with a Command and Control server located overseas.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1059 ? | ผู้โจมตีได้ส่งคำสั่งผ่านทาง PowerShell เพื่อดาวน์โหลดไฟล์สคริปต์ |
| 2 | described | T1497 ? | มีการตรวจสอบสภาพแวดล้อมของเครื่องเพื่อตรวจหาการทำงานภายในสภาพแวดล้อมเสมือน โดยตรวจสอบการมีอยู่ของเครื่องมือ virtualization ทั่วไป |
| 3 | named | T1568 ? | ผู้โจมตีได้ใช้ Dynamic Resolution เพื่อแปลงชื่อโดเมนที่ซ่อนไว้ให้เป็นที่อยู่ IP ที่เปลี่ยนแปลงได้ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_009  (source: C0018 (C0018, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบ web application ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต โดยผู้โจมตีใช้ Exploit Public-Facing Application ที่มีช่องโหว่ในหน้า login portal จากการตรวจสอบ Windows event log พบว่าผู้โจมตีได้ทำการเรียก WMI command เพื่อดำเนินการคำสั่งระบบจากระยะไกล ต่อมาจากการวิเคราะห์ network traffic พบการค้นหาข้อมูลการตั้งค่าเครือข่ายและรายชื่ออุปกรณ์ที่เชื่อมต่อในโดเมนภายใน จากนั้นผู้โจมตีใช้เครื่องมือ Software Deployment Tools ที่มีอยู่แล้วในสภาวะแวดล้อม เพื่อขยายการควบคุมไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่าย สุดท้ายจากการตรวจสอบ DNS query log และ firewall log พบการเชื่อมต่อไปยังเซิร์ฟเวอร์ภายนอกผ่าน Non-Standard Port 8843 และระบบไฟล์ทั้งหมดในเซิร์ฟเวอร์ถูกเข้ารหัส ทำให้ไม่สามารถเข้าถึงข้อมูลได้

*EN:* On 22 February 2569, an information technology private company in Bangkok province reported unauthorized access to the company's web application system. The attacker exploited a Exploit Public-Facing Application vulnerability in the login portal page. From examination of Windows event logs, it was found that the attacker executed WMI commands to perform system operations remotely. Subsequently, analysis of network traffic revealed queries for network configuration information and lists of connected devices within the domain. The attacker then used Software Deployment Tools already present in the environment to expand control to other servers on the network. Finally, from examination of DNS query logs and firewall logs, connections were found to external servers via Non-Standard Port 8843, and all file systems on the servers were encrypted, making data inaccessible.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1190 exploit public-facing application | ผู้โจมตีใช้ Exploit Public-Facing Application ที่มีช่องโหว่ในหน้า login portal |
| 2 | described | T1047 windows management instrumentation | ผู้โจมตีได้ทำการเรียก WMI command เพื่อดำเนินการคำสั่งระบบจากระยะไกล |
| 3 | described | T1016 ? | พบการค้นหาข้อมูลการตั้งค่าเครือข่ายและรายชื่ออุปกรณ์ที่เชื่อมต่อในโดเมนภายใน |
| 4 | named | T1072 software deployment tools | ผู้โจมตีใช้เครื่องมือ Software Deployment Tools ที่มีอยู่แล้วในสภาวะแวดล้อม เพื่อขยายการควบคุมไปยังเซิร์ฟเวอร์อื่นๆ |
| 5 | named | T1571 non-standard port | พบการเชื่อมต่อไปยังเซิร์ฟเวอร์ภายนอกผ่าน Non-Standard Port 8843 |
| 6 | described | T1486 data encrypted for impact | ระบบไฟล์ทั้งหมดในเซิร์ฟเวอร์ถูกเข้ารหัส ทำให้ไม่สามารถเข้าถึงข้อมูลได้ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_010  (source: C0027 (C0027, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log และ firewall พบว่าผู้โจมตีได้ใช้ External Remote Services ผ่านพอร์ต 3389 เพื่อเข้าสู่ระบบจากภายนอก ต่อมาจากการวิเคราะห์ network traffic พบว่าผู้โจมตีได้ทำการสแกนและเก็บรวบรวมข้อมูลเกี่ยวกับบริการเครือข่ายที่ทำงานอยู่บนเซิร์ฟเวอร์อื่น ๆ ในโครงข่ายภายในเพื่อค้นหาจุดอ่อน จากนั้นจากการตรวจสอบพยานหลักฐานดิจิทัลพบว่าผู้โจมตีได้ตั้งค่าการเชื่อมต่อผ่านเซิร์ฟเวอร์ proxy ระหว่างกลางเพื่อปกปิดการสื่อสารและคำสั่งควบคุมไปยังเซิร์ฟเวอร์ C2 ของตนเอง

*EN:* On 22 February 2026, a logistics services company in Samut Prakan Province reported unauthorized access to its primary server system. Log and firewall analysis revealed that the attacker used External Remote Services via port 3389 to gain initial access from outside the network. Subsequently, network traffic analysis showed the attacker conducted scanning and enumeration of network services running on other servers within the internal infrastructure to identify vulnerabilities. Upon examination of digital evidence, the attacker was found to have configured connections through an intermediate proxy server to conceal command-and-control communications with their remote infrastructure.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1133 external remote services | ผู้โจมตีได้ใช้ External Remote Services ผ่านพอร์ต 3389 |
| 2 | described | T1046 network service discovery | ผู้โจมตีได้ทำการสแกนและเก็บรวบรวมข้อมูลเกี่ยวกับบริการเครือข่ายที่ทำงานอยู่บนเซิร์ฟเวอร์อื่น ๆ ในโครงข่ายภายใน |
| 3 | described | T1090 ? | ผู้โจมตีได้ตั้งค่าการเชื่อมต่อผ่านเซิร์ฟเวอร์ proxy ระหว่างกลางเพื่อปกปิดการสื่อสารและคำสั่งควบคุม |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_011  (source: RedPenguin (C0056, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการโลจิสติกส์แห่งหนึ่งในจังหวัดสมุทรปราการแจ้งความว่าระบบคอมพิวเตอร์สำนักงานหลักถูกเข้าถึงข้อมูลโดยไม่ได้รับอนุญาต จากการตรวจสอบ log ระบบ พบว่าผู้โจมตีได้ใช้บัญชีพนักงานที่ยังมีสิทธิการใช้งานอยู่ของพนักงานคนหนึ่งที่ลาออกแล้ว เพื่อเข้าสู่เครือข่ายภายใน ต่อมาจากการตรวจสอบพยานหลักฐานดิจิทัลพบว่าผู้โจมตีได้ตั้งค่า Traffic Signaling บนอุปกรณ์เครือข่ายเพื่อให้คงอยู่ในระบบได้ยาวนาน จากนั้นผู้โจมตีได้ทำการสำรวจกระบวนการทำงานและเครื่องมือต่างๆ ที่ติดตั้งอยู่บนเซิร์ฟเวอร์ โดยการเรียกใช้คำสั่งระบบและตรวจสอบรายการเครื่องมือที่กำลังทำงาน สุดท้ายผู้โจมตีได้ใช้ Multi-Stage Channels สำหรับการสื่อสารแบบซ่อนเร้นกับเซิร์ฟเวอร์ควบคุมจากภายนอก และทำการ Exfiltration Over C2 Channel โดยส่งข้อมูลลูกค้า ข้อมูลการจัดส่ง และรายละเอียดบัญชีธนาคารจำนวนมากผ่านช่องทางการสื่อสารดังกล่าว

*EN:* On 22 February 2569, a logistics service company in Samut Prakan Province reported unauthorized access to its headquarters computer system. Log examination revealed that the attacker used valid employee credentials from a former employee who had already left the company to access the internal network. Subsequently, digital forensic examination found that the attacker had configured Traffic Signaling on network devices to maintain persistence in the system. The attacker then conducted reconnaissance of running processes and installed tools on servers by executing system commands and checking active processes. Finally, the attacker employed Multi-Stage Channels for covert communication with an external command server and performed Exfiltration Over C2 Channel, transmitting large quantities of customer data, shipment information, and bank account details through this communication channel.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1078 valid accounts | ผู้โจมตีได้ใช้บัญชีพนักงานที่ยังมีสิทธิการใช้งานอยู่ของพนักงานคนหนึ่งที่ลาออกแล้ว เพื่อเข้าสู่เครือข่ายภายใน |
| 2 | named | T1205 traffic signaling | ผู้โจมตีได้ตั้งค่า Traffic Signaling บนอุปกรณ์เครือข่ายเพื่อให้คงอยู่ในระบบได้ยาวนาน |
| 3 | described | T1057 ? | ผู้โจมตีได้ทำการสำรวจกระบวนการทำงานและเครื่องมือต่างๆ ที่ติดตั้งอยู่บนเซิร์ฟเวอร์ โดยการเรียกใช้คำสั่งระบบและตรวจสอบรายการเครื่องมือที่กำลังทำงาน |
| 4 | named | T1104 multi-stage channels | ผู้โจมตีได้ใช้ Multi-Stage Channels สำหรับการสื่อสารแบบซ่อนเร้นกับเซิร์ฟเวอร์ควบคุมจากภายนอก |
| 5 | named | T1041 ? | ทำการ Exfiltration Over C2 Channel โดยส่งข้อมูลลูกค้า ข้อมูลการจัดส่ง และรายละเอียดบัญชีธนาคารจำนวนมากผ่านช่องทางการสื่อสารดังกล่าว |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_012  (source: C0017 (C0017, campaign) )

**AUTO-FLAGS: step 3: described cue names the technique (access token manipulation)**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทให้บริการด้านการจัดการคลังสินค้าแห่งหนึ่งในจังหวัดสมุทรปราการได้แจ้งความว่าระบบ web application ของพวกเขาถูกบุกรุก จากการตรวจสอบ log พบว่า ผู้โจมตีได้ส่ง HTTP request ที่มีข้อมูล malicious payload ไปยัง endpoint ของระบบ inventory management ซึ่งมีช่องโหว่ไม่ได้ปิดปรับปรุงมาตั้งแต่เดือนที่แล้ว ต่อมาจากการวิเคราะห์ memory dump พบว่า execution flow ของ application ได้ถูกเปลี่ยนแปลง ทำให้โปรแกรมทำงานตามคำสั่งที่ผู้โจมตีกำหนด ไม่ใช่ตามที่ผู้พัฒนาตั้งใจไว้ จากนั้นผู้โจมตีได้ทำการ Access Token Manipulation โดยแก้ไข session token ในระบบเพื่อให้ได้สิทธิ์เข้าถึงระดับ administrator สุดท้ายจากการตรวจสอบ log access พบว่า ผู้โจมตีได้ทำการ System Owner/User Discovery เพื่อหาข้อมูลบัญชีผู้ใช้ในระบบ และทำการ Data from Local System โดยดึงข้อมูลลูกค้า รหัสสินค้า และข้อมูลการสั่งซื้อจากฐานข้อมูลภายใน ขณะเดียวกันพบการเชื่อมต่อ outbound traffic ไปยัง web service ภายนอกที่ไม่ได้รับการอนุญาต ซึ่งใช้เป็นช่องทางการสื่อสารและการส่งข้อมูลที่ขโมยได้

*EN:* On 22 February 2569, a warehouse management services company in Samut Prakan province reported that their web application system had been compromised. Log analysis revealed that the attacker sent HTTP requests with malicious payload to an endpoint of the inventory management system, exploiting an unpatched vulnerability from the previous month. Subsequently, memory dump analysis showed that the application's execution flow had been altered, causing the program to execute commands specified by the attacker rather than as intended by the developers. The attacker then performed Access Token Manipulation by modifying session tokens in the system to gain administrator-level privileges. Finally, access log review revealed that the attacker conducted System Owner/User Discovery to identify user accounts in the system and performed Data from Local System by extracting customer information, product codes, and purchase order data from the internal database. Simultaneously, outbound traffic connections to unauthorized external web services were identified, which served as command-and-control communication channels and data exfiltration pathways.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1190 exploit public-facing application | ส่ง HTTP request ที่มีข้อมูล malicious payload ไปยัง endpoint ของระบบ inventory management ซึ่งมีช่องโหว่ไม่ได้ปิดปรับปรุงมาตั้งแต่เดือนที่แล้ว |
| 2 | described | T1574 ? | execution flow ของ application ได้ถูกเปลี่ยนแปลง ทำให้โปรแกรมทำงานตามคำสั่งที่ผู้โจมตีกำหนด ไม่ใช่ตามที่ผู้พัฒนาตั้งใจไว้ |
| 3 | described | T1134 access token manipulation | ทำการ Access Token Manipulation โดยแก้ไข session token ในระบบเพื่อให้ได้สิทธิ์เข้าถึงระดับ administrator |
| 4 | named | T1033 system owner/user discovery | ทำการ System Owner/User Discovery เพื่อหาข้อมูลบัญชีผู้ใช้ในระบบ |
| 5 | named | T1005 ? | ทำการ Data from Local System โดยดึงข้อมูลลูกค้า รหัสสินค้า และข้อมูลการสั่งซื้อจากฐานข้อมูลภายใน |
| 6 | described | T1102 ? | การเชื่อมต่อ outbound traffic ไปยัง web service ภายนอกที่ไม่ได้รับการอนุญาต ซึ่งใช้เป็นช่องทางการสื่อสารและการส่งข้อมูลที่ขโมยได้ |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_013  (source: KV Botnet Activity (C0035, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านเทคโนโลยีสารสนเทศแห่งหนึ่งในจังหวัดกรุงเทพมหานครแจ้งความว่าระบบเซิร์ฟเวอร์หลักถูกบุกรุก จากการตรวจสอบ log พบว่าผู้โจมตีได้ใช้ Event Triggered Execution ผ่านงาน scheduled task เพื่อดำเนินการโดยมีสิทธิ์สูงขึ้น ต่อมาจากการวิเคราะห์ traffic และการตรวจสอบไฟล์ในระบบพบว่ามีการสำรวจการกำหนดค่าเครือข่ายอย่างละเอียด โดยดึงข้อมูลเกี่ยวกับการตั้งค่า routing, DNS records และการเชื่อมต่อเครือข่ายภายในองค์กร จากนั้นจากการตรวจสอบ firewall logs และ netstat records พบว่ามีการสื่อสารออกไปยังที่อยู่ IP ภายนอกผ่าน Non-Standard Port 8843 ซึ่งไม่ใช่พอร์ตมาตรฐานสำหรับบริการใด ๆ ในระบบ

*EN:* On 22 February 2569, a private-sector information technology company in Bangkok reported that its primary server system had been breached. From examination of logs, it was found that the attacker had used Event Triggered Execution via a scheduled task to perform actions with elevated privileges. Subsequently, through analysis of traffic and file system examination, detailed reconnaissance of network configuration was discovered, with extraction of information regarding routing settings, DNS records, and internal organizational network connectivity. Then, from examination of firewall logs and netstat records, outbound communication was identified to an external IP address via Non-Standard Port 8843, which is not a standard port for any service in the system.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1546 ? | ใช้ Event Triggered Execution ผ่านงาน scheduled task เพื่อดำเนินการโดยมีสิทธิ์สูงขึ้น |
| 2 | described | T1016 ? | มีการสำรวจการกำหนดค่าเครือข่ายอย่างละเอียด โดยดึงข้อมูลเกี่ยวกับการตั้งค่า routing, DNS records และการเชื่อมต่อเครือข่ายภายในองค์กร |
| 3 | named | T1571 non-standard port | มีการสื่อสารออกไปยังที่อยู่ IP ภายนอกผ่าน Non-Standard Port 8843 |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_014  (source: SharePoint ToolShell Exploitation (C0058, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบ web application ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต ผู้โจมตีใช้ประโยชน์จากช่องโหว่ในส่วน public-facing application ของระบบจัดการลูกค้า เข้าสู่เซิร์ฟเวอร์หลักของบริษัท จากการตรวจสอบ registry log พบว่าผู้โจมตีทำการ Modify Registry ในหลายจุดเพื่อให้ malware ทำงานอยู่ในเบื้องหลังอย่างต่อเนื่อง ต่อมาจากการวิเคราะห์ evidence พบร่องรอยของการค้นหาข้อมูลระบบ เช่น การอ่าน registry keys เกี่ยวกับเวอร์ชั่นระบบปฏิบัติการและรายชื่อซอฟต์แวร์ที่ติดตั้ง จากนั้นผู้โจมตีได้ส่ง exploitation tools และ malware ไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่ายภายในของบริษัท สุดท้ายระบบทั้งหมดในเครือข่ายถูกเข้ารหัสลับด้วย ransomware และผู้โจมตีขอค่าไถ่จากบริษัท

*EN:* On 22 February 2569, a financial services company in Bangkok reported unauthorized access to its web application system. The attacker exploited a vulnerability in the public-facing application of the customer management system to gain entry to the company's main server. Registry log analysis revealed that the attacker performed Modify Registry at multiple points to maintain malware persistence in the background. Subsequently, evidence analysis uncovered traces of system reconnaissance, such as reading registry keys related to operating system version and installed software inventory. The attacker then transferred exploitation tools and malware to other servers within the company's internal network. Finally, all systems in the network were encrypted with ransomware and the attacker demanded a ransom from the company.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1190 exploit public-facing application | ผู้โจมตีใช้ประโยชน์จากช่องโหว่ในส่วน public-facing application ของระบบจัดการลูกค้า เข้าสู่เซิร์ฟเวอร์หลักของบริษัท |
| 2 | named | T1112 modify registry | ทำการ Modify Registry ในหลายจุดเพื่อให้ malware ทำงานอยู่ในเบื้องหลังอย่างต่อเนื่อง |
| 3 | described | T1082 ? | พบร่องรอยของการค้นหาข้อมูลระบบ เช่น การอ่าน registry keys เกี่ยวกับเวอร์ชั่นระบบปฏิบัติการและรายชื่อซอฟต์แวร์ที่ติดตั้ง |
| 4 | described | T1570 lateral tool transfer | ผู้โจมตีได้ส่ง exploitation tools และ malware ไปยังเซิร์ฟเวอร์อื่นๆ ในเครือข่ายภายในของบริษัท |
| 5 | described | T1486 data encrypted for impact | ระบบทั้งหมดในเครือข่ายถูกเข้ารหัสลับด้วย ransomware และผู้โจมตีขอค่าไถ่จากบริษัท |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_015  (source: ArcaneDoor (C0046, campaign) )

**AUTO-FLAGS: step 1: described cue names the technique (external remote services)**

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทสื่อสารอเนกประสงค์แห่งหนึ่งในจังหวัดกรุงเทพมหานคร ได้รับแจ้งเบาะแสจากเจ้าหน้าที่ระบบว่ามีการเข้าถึง VPN gateway ของบริษัทจากแอดเรส IP ต่างประเทศหลายครั้งในช่วงเวลากลางคืน จากการตรวจสอบ log พบว่าผู้โจมตีได้เชื่อมต่อผ่านทาง external remote services โดยใช้ข้อมูลประจำตัวของพนักงานแผนกเทคนิก ต่อมาจากการวิเคราะห์ traffic บน network segment ระหว่างเซิร์ฟเวอร์ VPN และ domain controller พบหลักฐานการทำ network sniffing ด้วยเครื่องมือ packet capture ซึ่งผู้โจมตีได้บันทึก plaintext credentials ของผู้ใช้งานหลายราย จากนั้นจากการตรวจสอบเหตุการณ์บนเครื่องสถานีงานพบว่าเกิดการเรียก system commands เพื่อดึงข้อมูลเกี่ยวกับคุณลักษณะของระบบปฏิบัติการ เวอร์ชันซอฟต์แวร์ และรายชื่อซอฟต์แวร์ที่ติดตั้ง ซึ่งบ่งชี้ว่าผู้โจมตีทำการสำรวจสภาพแวดล้อมของระบบเป้าหมายเพื่อวางแผนการโจมตีขั้นต่อไป

*EN:* On 22 February 2569, a telecommunications company in Bangkok received notification from system administrators that the corporate VPN gateway had experienced multiple login attempts from foreign IP addresses during night hours. Upon examination of system logs, investigators determined that the attacker had established a connection through external remote services using credentials belonging to a technical department employee. Subsequently, analysis of network traffic between the VPN server and domain controller revealed evidence of network sniffing using packet capture tools, during which the attacker recorded plaintext credentials of multiple users. Following this, examination of workstation event logs disclosed execution of system commands designed to enumerate operating system characteristics, software versions, and installed application inventories, indicating the attacker was conducting reconnaissance of the target environment for further attack planning.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1133 external remote services | ผู้โจมตีได้เชื่อมต่อผ่านทาง external remote services โดยใช้ข้อมูลประจำตัวของพนักงานแผนกเทคนิก |
| 2 | named | T1040 network sniffing | จากการวิเคราะห์ traffic บน network segment ระหว่างเซิร์ฟเวอร์ VPN และ domain controller พบหลักฐานการทำ network sniffing ด้วยเครื่องมือ packet capture |
| 3 | described | T1082 ? | เกิดการเรียก system commands เพื่อดึงข้อมูลเกี่ยวกับคุณลักษณะของระบบปฏิบัติการ เวอร์ชันซอฟต์แวร์ และรายชื่อซอฟต์แวร์ที่ติดตั้ง |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_016  (source: Operation Sharpshooter (C0013, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ ได้รับแจ้งเบาะแสจากฝ่ายไอทีว่าระบบ workstation ของพนักงานสายบริหาร ถูกเข้าถึงข้อมูลโดยไม่ได้รับอนุญาต จากการตรวจสอบ log และ memory dump พบว่าผู้โจมตีได้ดำเนินการเรียกใช้ฟังก์ชัน Windows API โดยตรงผ่านสคริปต์ PowerShell เพื่อดำเนินการที่ซ่อนอยู่ในระบบ ต่อมาจากการวิเคราะห์ process tree พบว่ามีกิจกรรมการแทรกโค้ดลงในโปรแกรม explorer.exe เพื่อขยายสิทธิ์การเข้าถึงและบ่อนทำลายการป้องกัน จากนั้นผู้โจมตีได้ใช้ proxy เป็นช่องทางสื่อสารกับเซิร์ฟเวอร์ควบคุมภายนอกเพื่อส่งคำสั่งและดึงข้อมูลจากระบบต่อไป

*EN:* On 22 February 2569, a private financial services company in Bangkok received notice from the IT department that an executive workstation had been accessed without authorization. Upon examination of logs and memory dumps, it was found that the attacker had invoked Windows API functions directly via PowerShell script to execute hidden system operations. Subsequently, analysis of the process tree revealed code injection activity into explorer.exe to escalate access privileges and circumvent protections. The attacker then employed a proxy as a communication channel to a remote command-and-control server for issuing commands and exfiltrating data from the system.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1106 ? | ผู้โจมตีได้ดำเนินการเรียกใช้ฟังก์ชัน Windows API โดยตรงผ่านสคริปต์ PowerShell เพื่อดำเนินการที่ซ่อนอยู่ในระบบ |
| 2 | described | T1055 ? | มีกิจกรรมการแทรกโค้ดลงในโปรแกรม explorer.exe เพื่อขยายสิทธิ์การเข้าถึง |
| 3 | named | T1090 ? | ผู้โจมตีได้ใช้ proxy เป็นช่องทางสื่อสารกับเซิร์ฟเวอร์ควบคุมภายนอก |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_017  (source: C0032 (C0032, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านสื่อสารแห่งหนึ่งในจังหวัดกรุงเทพได้รับแจ้งเบาะแสจากผู้เสียหายว่าระบบ VPN และ SSH ของบริษัทถูกเข้าถึงโดยไม่ได้รับอนุญาต โดยผู้โจมตีใช้ External Remote Services ผ่านพอร์ตมาตรฐาน 22 และ 443 เพื่อเจาะเข้าสู่ระบบ จากการตรวจสอบ log พบว่าต่อมามีการเข้าสู่ระบบหลายครั้งโดยใช้บัญชีผู้ใช้ที่ชื่อ "sysadmin" และ "backup_service" ซึ่งเป็นบัญชีของเจ้าหน้าที่ที่ยังคงใช้งานอยู่ แม้ว่าคนเหล่านั้นไม่ได้ทำการเข้าสู่ระบบในช่วงเวลาดังกล่าว จากนั้นจากการตรวจสอบพยานหลักฐานดิจิทัลพบว่ามีการติดตั้ง backdoor ผ่านพอร์ต 8847 และพอร์ต 9443 ซึ่งไม่ใช่พอร์ตมาตรฐานสำหรับบริการใดๆ ของบริษัท เพื่อให้ผู้โจมตีสามารถรักษาการเชื่อมต่อและควบคุมระบบได้อย่างต่อเนื่อง

*EN:* On 22 February 2569, a private telecommunications company in Bangkok received notification from the victim that the company's VPN and SSH systems were accessed without authorization. The attacker used External Remote Services through standard ports 22 and 443 to penetrate the system. From log examination, it was found that subsequently there were multiple logins using user accounts named "sysadmin" and "backup_service", which were employee accounts still active, even though those individuals did not log in during the time in question. Subsequently, from digital forensic examination, it was discovered that a backdoor was installed through port 8847 and port 9443, which are non-standard ports not used by any legitimate service of the company, enabling the attacker to maintain persistent connection and control over the system.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1133 external remote services | ผู้โจมตีใช้ External Remote Services ผ่านพอร์ตมาตรฐาน 22 และ 443 |
| 2 | described | T1078 valid accounts | มีการเข้าสู่ระบบหลายครั้งโดยใช้บัญชีผู้ใช้ที่ชื่อ "sysadmin" และ "backup_service" ซึ่งเป็นบัญชีของเจ้าหน้าที่ที่ยังคงใช้งานอยู่ แม้ว่าคนเหล่านั้นไม่ได้ทำการเข้าสู่ระบบในช่วงเวลาดังกล่าว |
| 3 | described | T1571 non-standard port | มีการติดตั้ง backdoor ผ่านพอร์ต 8847 และพอร์ต 9443 ซึ่งไม่ใช่พอร์ตมาตรฐานสำหรับบริการใดๆ ของบริษัท |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_018  (source: SolarWinds Compromise (C0024, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพได้แจ้งความว่าระบบ customer portal ถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีใช้ Exploit Public-Facing Application ผ่านช่องโหว่ XML external entity ในฟังก์ชัน document upload เพื่อเข้าถึงระบบ ต่อมาผู้โจมตีทำการ Steal Web Session Cookie โดยการดักจับ HTTP traffic และนำ session token ไปใช้ในการเข้าถึงบัญชีผู้ใช้งาน จากนั้นผู้โจมตีทำการ Account Discovery เพื่อค้นหารายชื่อบัญชีผู้ใช้งานอื่น ๆ ในระบบ โดยการส่ง API query ที่ไม่ได้รับการตรวจสอบสิทธิ์ สุดท้ายจากการวิเคราะห์ evidence พบร่องรอยการใช้ session cookie ของบัญชี admin ในการเข้าถึงระบบจากที่อยู่ IP ที่ไม่ตรงกับรูปแบบการใช้งานปกติ ซึ่งบ่งชี้ว่าผู้โจมตีได้นำ credential material ที่ขโมยมาใช้ในการเข้าถึงบัญชีระดับสูงเพิ่มเติม

*EN:* On 22 February 2569, a private financial services company in Bangkok reported unauthorized access to its customer portal system. Log analysis revealed that the attacker used Exploit Public-Facing Application by exploiting an XML external entity vulnerability in the document upload function to gain system access. Subsequently, the attacker performed Steal Web Session Cookie by intercepting HTTP traffic and capturing session tokens to access user accounts. The attacker then conducted Account Discovery by sending unvalidated API queries to enumerate additional usernames in the system. Finally, evidence analysis identified traces of an admin account's session cookie being used to access the system from IP addresses inconsistent with normal usage patterns, indicating the attacker had leveraged stolen credential material to access higher-privileged accounts.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | named | T1190 exploit public-facing application | ผู้โจมตีใช้ Exploit Public-Facing Application ผ่านช่องโหว่ XML external entity ในฟังก์ชัน document upload |
| 2 | named | T1539 steal web session cookie | ผู้โจมตีทำการ Steal Web Session Cookie โดยการดักจับ HTTP traffic และนำ session token ไปใช้ในการเข้าถึงบัญชีผู้ใช้งาน |
| 3 | named | T1087 account discovery | ผู้โจมตีทำการ Account Discovery เพื่อค้นหารายชื่อบัญชีผู้ใช้งานอื่น ๆ ในระบบ โดยการส่ง API query ที่ไม่ได้รับการตรวจสอบสิทธิ์ |
| 4 | described | T1550 use alternate authentication material | ผู้โจมตีได้นำ credential material ที่ขโมยมาใช้ในการเข้าถึงบัญชีระดับสูงเพิ่มเติม |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_019  (source: C0026 (C0026, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนด้านการเงินแห่งหนึ่งในจังหวัดกรุงเทพฯ แจ้งความว่าระบบ server ของพวกเขาถูกเข้าถึงโดยไม่ได้รับอนุญาต จากการตรวจสอบ log พบว่าผู้โจมตีได้ทำการสแกนและเก็บรวบรวมข้อมูลจากเครื่องคอมพิวเตอร์ในเครือข่ายภายในองค์กร รวมถึงรายชื่อผู้ใช้ และไฟล์การกำหนดค่าระบบต่างๆ ต่อมา ผู้โจมตีใช้ Dynamic Resolution เพื่อเชื่อมต่อไปยังเซิร์ฟเวอร์ command-and-control ที่มีโดเมนเปลี่ยนแปลงอยู่ตลอดเวลา จากนั้นระบบเริ่มส่งข้อมูลที่ได้เก็บรวบรวมออกจากเครือข่ายในรูปแบบแบ่งส่วนเป็นชุดเล็กๆ ตามขนาดที่จำกัด เพื่อหลีกเลี่ยงการตรวจจับโดยระบบ IDS และ firewall สุดท้าย จากการติดตามการเคลื่อนไหวของแพ็กเก็ต พบว่าข้อมูลทั้งหมดได้ถูกส่งออกไปนอกประเทศเรียบร้อยแล้ว

*EN:* On 22 February 2569, a private financial company in Bangkok reported unauthorized access to its server systems. Upon examination of system logs, investigators found that the attacker had scanned and collected data from computers within the organization's network, including usernames and system configuration files. Subsequently, the attacker used Dynamic Resolution to connect to command-and-control servers with continuously changing domains. The system then began exfiltrating the collected data in small segmented chunks with size restrictions to evade detection by IDS and firewall systems. Finally, through packet monitoring, it was confirmed that all data had been successfully transferred out of the country.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1005 ? | ผู้โจมตีได้ทำการสแกนและเก็บรวบรวมข้อมูลจากเครื่องคอมพิวเตอร์ในเครือข่ายภายในองค์กร รวมถึงรายชื่อผู้ใช้ และไฟล์การกำหนดค่าระบบต่างๆ |
| 2 | named | T1568 ? | ผู้โจมตีใช้ Dynamic Resolution เพื่อเชื่อมต่อไปยังเซิร์ฟเวอร์ command-and-control ที่มีโดเมนเปลี่ยนแปลงอยู่ตลอดเวลา |
| 3 | described | T1030 data transfer size limits | ระบบเริ่มส่งข้อมูลที่ได้เก็บรวบรวมออกจากเครือข่ายในรูปแบบแบ่งส่วนเป็นชุดเล็กๆ ตามขนาดที่จำกัด เพื่อหลีกเลี่ยงการตรวจจับโดยระบบ IDS และ firewall |

- [ ] ผ่าน / แก้แล้ว

## inc_camp_020  (source: Operation Digital Eye (C0061, campaign) )

> เมื่อวันที่ 22 กุมภาพันธ์ 2569 บริษัทเอกชนแห่งหนึ่งในจังหวัดนครปฐม ซึ่งประกอบธุรกิจด้านการจัดการโลจิสติกส์ แจ้งความว่าระบบเว็บแอปพลิเคชันสำหรับการจัดการใบสั่งซื้อถูกบุกรุก โดยผู้โจมตีได้ส่งคำขอ HTTP แบบพิเศษไปยังฟังก์ชัน API endpoint ที่มีช่องโหว่ในการตรวจสอบอนุญาต จากการตรวจสอบ log พบว่า ผู้โจมตีได้ใช้ Native API เพื่อดำเนินการคำสั่งในระบบและอ่านข้อมูลจากหน่วยความจำ ต่อมาผู้โจมตีทำการ System Owner/User Discovery โดยการสอบถามข้อมูลบัญชีผู้ใช้งานและสิทธิการเข้าถึงระบบผ่านทาง WMI query จากนั้นพบว่าผู้โจมตีได้ซ่อนโครงสร้างพื้นฐานของตนเองโดยการใช้ proxy ชั้นกลางและ DNS tunneling เพื่อซ่อนการเชื่อมต่อกับเซิร์ฟเวอร์ command and control ทำให้การติดตามแหล่งที่มาของการโจมตีเป็นไปได้ยาก

*EN:* On 22 February 2569, a private logistics management company in Nakhon Pathom province reported that its web application system for purchase order management had been compromised. Investigators found that the attacker had sent specially crafted HTTP requests to an API endpoint with authorization validation flaws. Log examination revealed the attacker had used Native API to execute commands within the system and read data from memory. Subsequently, the attacker performed System Owner/User Discovery by querying user account information and system access privileges via WMI queries. It was then discovered that the attacker had hidden their infrastructure by using intermediate proxies and DNS tunneling to obscure connections to the command and control server, making source tracing difficult.

| # | cue_type | technique | cue |
|---|----------|-----------|-----|
| 1 | described | T1190 exploit public-facing application | ผู้โจมตีได้ส่งคำขอ HTTP แบบพิเศษไปยังฟังก์ชัน API endpoint ที่มีช่องโหว่ในการตรวจสอบอนุญาต |
| 2 | named | T1106 ? | ผู้โจมตีได้ใช้ Native API เพื่อดำเนินการคำสั่งในระบบและอ่านข้อมูลจากหน่วยความจำ |
| 3 | named | T1033 system owner/user discovery | ผู้โจมตีทำการ System Owner/User Discovery โดยการสอบถามข้อมูลบัญชีผู้ใช้งานและสิทธิการเข้าถึงระบบผ่านทาง WMI query |
| 4 | described | T1665 hide infrastructure | ผู้โจมตีได้ซ่อนโครงสร้างพื้นฐานของตนเองโดยการใช้ proxy ชั้นกลางและ DNS tunneling เพื่อซ่อนการเชื่อมต่อกับเซิร์ฟเวอร์ command and control |

- [ ] ผ่าน / แก้แล้ว
