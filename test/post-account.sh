for i in {1..10}
do
    curl -X POST http://127.0.0.1:8081/accounts --data "currency=USD" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
    printf "\n"
done


for i in {1..10}
do
    curl -X POST http://127.0.0.1:8081/accounts --data "currency=EUR" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
    printf "\n"
done
