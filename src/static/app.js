angular.module('twisted-rest-example', ['restangular', 'ngRoute'])
    .factory('tokenInterceptor', function ($rootScope) {
        return {
            request: function(config) {
                config.headers["Authorization"] = $rootScope.token;
                return config;
            }
        };
    })

    .service('paging', function() {
        this.init = function($scope, refresh_func) {
            $scope.page_num = 0;
            $scope.paged = true;
            $scope.next_page = function() {
                $scope.page_num++;
                refresh_func();
            };
            $scope.prev_page = function() {
                if ($scope.page_num > 0) {
                    $scope.page_num--;
                    refresh_func();
                }
            };
        };
    })

    .service('url_encoder', function() {
        this.encode = function(data) {
            res = "";
            for (i in data) 
                if (data[i]) {
                    if (res)
                        res += "&";
                    res += i + "=" + encodeURIComponent(data[i]);
                }
            return res;
        };
    })

    .service('error_handler', function(Restangular) {
        this.init = function($scope) {
            scope = $scope;
            Restangular.setErrorInterceptor(
                function(res) {
                    scope.last_error = JSON.stringify(res);
                    return true;
                }
            );
        };
        this.wrap = function($scope, cb) {
            scope = $scope;
            return function(res) {
                if (res.error) {
                    scope.last_error = res.message;
                } else {
                    scope.last_error = false;
                    cb(res);
                }

            };
        };
    })

    .config(function($routeProvider, $httpProvider, RestangularProvider) {
        $routeProvider
            .when('/landing', {
                controller: LandingCtrl,
                templateUrl: 'landing.html'
            })
            .when('/account-detail/:account_id', {
                controller: AccountDetailCtrl,
                templateUrl: 'account-detail.html'
            })
            .when('/new-account', {
                controller: NewAccountCtrl,
                templateUrl: 'new-account.html'
            })
            .when('/new-transaction', {
                controller: NewTransactionCtrl,
                templateUrl: 'new-transaction.html'
            })
        
        ;

        $httpProvider.interceptors.push('tokenInterceptor');
        RestangularProvider.setResponseExtractor(function(response, operation) {
            if (operation === 'getList') {
                var newResponse = response.data;
                newResponse.error = response.error;
                if (newResponse.error) {
                    newResponse.message = response.message;
                    newResponse.code = response.code;
                }
                
                return newResponse;
            }
            return response;
        });
    })

    .run(['$rootScope', '$location', 'Restangular',
          function ($rootScope, $location, Restangular) {
              
              $rootScope.token = "25184bc5947ed61556d5230a79394fdd43cdcc04";

              $rootScope.go_landing = function() {
                  $location.path("/landing");
              };
              $rootScope.new_account = function() {
                  $location.path("/new-account");
              };
              $rootScope.new_transaction = function() {
                  $location.path("/new-transaction");
              };
              
              $location.path("/landing");
          }])
;



function LandingCtrl($scope, $location, Restangular, paging, error_handler) {
    error_handler.init($scope);
    
    refresh = function() {
        Restangular.all('/accounts?page=' + $scope.page_num).getList()            .then(error_handler.wrap($scope, function(res) {
            $scope.accounts = res;            
        }));
    };
    paging.init($scope, refresh);
    $scope.show_detail = function(account_id) {
        $location.path("/account-detail/" + account_id);
    };
    refresh();
}

function AccountDetailCtrl($scope, $location, Restangular,
                           $routeParams, paging, error_handler) {
    error_handler.init($scope);
    var account_id = $routeParams.account_id;
    $scope.account_id = account_id;
    
    refresh = function() {
    
        var url = '/transactions/account/' + account_id +
            '?page=' + $scope.page_num;
        Restangular.all(url).getList()
            .then(error_handler.wrap($scope, function(res) {
                $scope.transactions = res;
            }));
    };
    paging.init($scope, refresh);
    refresh();
}

function NewAccountCtrl($scope, $location, Restangular, url_encoder, error_handler) {
    error_handler.init($scope);

    $scope.do_create = function() {
        var data = {
            "currency": $scope.currency
        };
        data = url_encoder.encode(data);
        Restangular.oneUrl('/accounts')
            .customPOST(
                data, undefined, undefined,
                {'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8"}
            )
            .then(error_handler.wrap($scope, function(res) {
                $scope.last_account_id = res.data.accountId;    
            }));        
    }
    Restangular.all('/currencies').getList()
        .then(
            function(res) {
                $scope.currencies = res;
            });

}

function NewTransactionCtrl($scope, $location, Restangular, url_encoder, error_handler) {
    error_handler.init($scope);

    $scope.do_create = function() {
        var data = {
            "sourceAccount": $scope.source_id,
            "destAccount": $scope.dest_id,
            "amount": $scope.amount
        };
        data = url_encoder.encode(data);
        Restangular.oneUrl('/transactions')
            .customPOST(
                data, undefined, undefined,
                {'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8"}
            )
            .then(error_handler.wrap($scope, function(res) {
                $scope.last_transaction_id = res.data.transactionId;
            }));
    }
}
