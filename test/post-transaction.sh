for i in {10000001..10000005}
do
    curl -X POST http://127.0.0.1:8081/transactions --data "destAccount=$i&amount=100.7" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
    printf "\n"
done


for i in {10000001..10000005}
do
    curl -X POST http://127.0.0.1:8081/transactions --data "sourceAccount=$i&amount=10.7&destAccount=10000007" -H 'Authorization: 25184bc5947ed61556d5230a79394fdd43cdcc04'
    printf "\n"
done


