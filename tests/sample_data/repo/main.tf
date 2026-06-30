resource "aws_instance" "web" {
  ami           = "ami-123456"
  instance_type = "t3.micro"
}

resource "aws_security_group" "web" {
  name = "web"
}
