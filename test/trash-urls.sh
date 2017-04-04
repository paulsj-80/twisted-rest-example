
curl -X POST http://127.0.0.1:8081/transactions --data "sourceAccount=10000002&amount=1000000.7&destAccount=10000007" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"


curl -X POST http://127.0.0.1:8081/transactions --data "sourceAccount=$123&amount=1.7&destAccount=10000007" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"

curl -X POST http://127.0.0.1:8081/accounts --data "currencyzz=USD" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"

curl -X GET http://127.0.0.1:8081/fofofof -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"


curl -X POST http://127.0.0.1:8081/fofofof -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"

curl -X POST http://127.0.0.1:8081/fofofof/123 -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"

curl -X GET http://127.0.0.1:8081/accounts/abra/dfdf -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
printf "\n"




